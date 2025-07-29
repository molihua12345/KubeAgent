#!/usr/bin/env python3
"""
通用数据处理脚本
将application、trace、log数据整合为CTH格式的JSON数据
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse


class DataProcessor:
    """数据处理器，用于将多个服务的数据整合为CTH格式"""
    
    def __init__(self):
        self.services = set()
        self.service_traces = {}  # 按服务存储trace数据
        self.service_metrics = {}  # 按服务存储metric数据
        self.service_logs = {}  # 按服务存储log数据
    
    def load_json_file(self, file_path: str) -> Dict[str, Any]:
        """加载JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return {}
    
    def timestamp_to_iso(self, timestamp: int) -> str:
        """将毫秒时间戳转换为ISO格式字符串"""
        return datetime.fromtimestamp(timestamp / 1000).isoformat() + 'Z'
    
    def extract_service_name(self, service_id: str) -> str:
        """从服务ID中提取服务名称"""
        # 处理格式如: "default:Deployment:frontend" -> "frontend"
        # 或 "/k8s/default/frontend" -> "frontend"
        if ':' in service_id:
            return service_id.split(':')[-1]
        elif '/' in service_id:
            return service_id.split('/')[-1]
        return service_id
    
    def process_trace_data(self, trace_data: Dict[str, Any]) -> None:
        """处理trace数据"""
        if 'data' not in trace_data or 'spans' not in trace_data['data']:
            return
        
        spans = trace_data['data']['spans']
        if spans is None:
            return
        
        # 按服务分组spans，只保留最新的trace
        for span in spans:
            service_name = self.extract_service_name(span.get('service', ''))
            trace_id = span.get('trace_id')
            timestamp = span.get('timestamp', 0)
            
            # 转换span格式
            converted_span = {
                'service': service_name,
                'operation': span.get('name', ''),
                'start_time': self.timestamp_to_iso(timestamp),
                'end_time': self.timestamp_to_iso(timestamp + span.get('duration', 0)),
                'status': 'error' if span.get('status', {}).get('error', False) else 'ok',
                'tags': {
                    'pod': span.get('attributes', {}).get('container.id', '').split('/')[-1] if span.get('attributes', {}).get('container.id') else '',
                    'node': span.get('attributes', {}).get('host.name', ''),
                    'trace_id': trace_id
                }
            }
            
            # 添加服务到集合
            self.services.add(service_name)
            
            # 只保留每个服务最新的trace数据
            if service_name not in self.service_traces or timestamp > self.service_traces[service_name]['latest_timestamp']:
                self.service_traces[service_name] = {
                    'trace_id': trace_id,
                    'spans': [converted_span],
                    'latest_timestamp': timestamp
                }
            elif timestamp == self.service_traces[service_name]['latest_timestamp']:
                # 如果时间戳相同，添加到同一个trace中
                self.service_traces[service_name]['spans'].append(converted_span)
    
    def process_log_data(self, log_data: Dict[str, Any]) -> None:
        """处理log数据"""
        if 'data' not in log_data or 'entries' not in log_data['data']:
            return
        
        entries = log_data['data']['entries']
        if entries is None:
            return
        
        for entry in entries:
            service_name = self.extract_service_name(
                entry.get('attributes', {}).get('service.name', '')
            )
            timestamp = entry.get('timestamp', 0)
            
            converted_log = {
                'entity': service_name,
                'message': entry.get('message', ''),
                'level': entry.get('severity', 'info'),
                'timestamp': self.timestamp_to_iso(timestamp),
                'tags': {
                    'pod': entry.get('attributes', {}).get('container.id', '').split('/')[-1] if entry.get('attributes', {}).get('container.id') else '',
                    'host': entry.get('attributes', {}).get('host.name', ''),
                    'pattern_hash': entry.get('attributes', {}).get('pattern.hash', '')
                }
            }
            
            # 添加服务到集合
            self.services.add(service_name)
            
            # 只保留每个服务最新的log数据
            if service_name not in self.service_logs or timestamp > self.service_logs[service_name]['latest_timestamp']:
                self.service_logs[service_name] = {
                    'log_data': converted_log,
                    'latest_timestamp': timestamp
                }
    
    def process_application_data(self, app_data: Dict[str, Any]) -> None:
        """处理application数据，生成metrics"""
        if 'data' not in app_data or 'app_map' not in app_data['data']:
            return
        
        app_map = app_data['data']['app_map']
        if app_map is None:
            return
        application = app_map.get('application', {})
        
        service_name = self.extract_service_name(application.get('id', ''))
        self.services.add(service_name)
        
        # 从indicators生成metrics，只保留最新的
        current_time = datetime.now()
        current_timestamp = int(current_time.timestamp() * 1000)
        current_time_iso = current_time.isoformat() + 'Z'
        
        service_metrics = []
        indicators = application.get('indicators', [])
        if indicators is not None:
            for indicator in indicators:
                metric_name = indicator.get('message', '').lower().replace(' ', '_')
                is_anomalous = indicator.get('status') in ['warning', 'critical', 'error']
                
                # 根据状态生成模拟的metric值
                value = self._generate_metric_value(metric_name, indicator.get('status', 'ok'))
                
                metric = {
                    'entity': service_name,
                    'metric_name': metric_name,
                    'value': value,
                    'timestamp': current_time_iso,
                    'is_anomalous': is_anomalous,
                    'tags': {
                        'namespace': application.get('labels', {}).get('ns', 'default'),
                        'status': indicator.get('status', 'ok')
                    }
                }
                
                service_metrics.append(metric)
        
        # 只保留每个服务最新的metrics
        if service_name not in self.service_metrics or current_timestamp > self.service_metrics[service_name]['latest_timestamp']:
            self.service_metrics[service_name] = {
                'metrics': service_metrics,
                'latest_timestamp': current_timestamp
            }
        
        # 处理依赖关系，生成连接metrics
        instances = app_map.get('instances', [])
        if instances is not None:
            for instance in instances:
                dependencies = instance.get('dependencies', [])
                if dependencies is not None:
                    for dep in dependencies:
                        dep_service = self.extract_service_name(dep.get('id', ''))
                
                # 从stats中提取数值
                stats = dep.get('stats', [])
                if stats:
                    # 解析类似 "📈 4 rps ⏱️ 6ms" 的统计信息
                    for stat in stats:
                        if 'rps' in stat and 'ms' in stat:
                            try:
                                # 提取RPS和延迟
                                parts = stat.split()
                                rps_idx = next(i for i, part in enumerate(parts) if 'rps' in part)
                                ms_idx = next(i for i, part in enumerate(parts) if 'ms' in part)
                                
                                rps_value = float(parts[rps_idx-1])
                                latency_value = float(parts[ms_idx-1].replace('⏱️', ''))
                                
                                # 生成RPS metric
                                service_metrics.append({
                                    'entity': f"{service_name}->{dep_service}",
                                    'metric_name': 'request_rate',
                                    'value': rps_value,
                                    'timestamp': current_time_iso,
                                    'is_anomalous': dep.get('status') != 'ok',
                                    'tags': {
                                        'source': service_name,
                                        'target': dep_service,
                                        'direction': dep.get('direction', 'to')
                                    }
                                })
                                
                                # 生成延迟metric
                                service_metrics.append({
                                    'entity': f"{service_name}->{dep_service}",
                                    'metric_name': 'response_time',
                                    'value': latency_value,
                                    'timestamp': current_time_iso,
                                    'is_anomalous': latency_value > 100,  # 假设>100ms为异常
                                    'tags': {
                                        'source': service_name,
                                        'target': dep_service,
                                        'direction': dep.get('direction', 'to')
                                    }
                                })
                            except (ValueError, StopIteration):
                                continue
    
    def _generate_metric_value(self, metric_name: str, status: str) -> float:
        """根据metric名称和状态生成模拟的数值"""
        base_values = {
            'slo': 0.99,
            'instances': 3,
            'cpu': 0.5,
            'memory': 0.7,
            'net': 1000,
            'logs': 10
        }
        
        base_value = base_values.get(metric_name, 1.0)
        
        # 根据状态调整值
        if status == 'critical':
            return base_value * 2.5
        elif status == 'warning':
            return base_value * 1.5
        elif status == 'error':
            return base_value * 3.0
        else:
            return base_value
    
    def process_json_data(self, json_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理JSON数据列表并返回CTH格式的数据"""
        for data_item in json_data_list:
            if not data_item or 'data_type' not in data_item:
                print("Invalid data item: missing data_type")
                continue
            
            data_type = data_item['data_type'].lower()
            data = data_item.get('data', {})
            
            if not data:
                print(f"No data found in {data_type} item")
                continue
            
            print(f"Processing {data_type} data...")
            
            if data_type == 'trace':
                self.process_trace_data(data)
            elif data_type == 'log':
                self.process_log_data(data)
            elif data_type == 'application':
                self.process_application_data(data)
            else:
                print(f"Unknown data type: {data_type}")
        
        return self._aggregate_results()
    
    def process_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """处理多个文件并返回CTH格式的数据"""
        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                continue
            
            print(f"Processing {file_path}...")
            data = self.load_json_file(file_path)
            
            if not data:
                continue
            
            # 根据文件名判断数据类型
            filename = os.path.basename(file_path).lower()
            
            if 'trace' in filename:
                self.process_trace_data(data)
            elif 'log' in filename:
                self.process_log_data(data)
            elif 'application' in filename:
                self.process_application_data(data)
            else:
                print(f"Unknown file type: {filename}")
        
        return self._aggregate_results()
    
    def _aggregate_results(self) -> Dict[str, Any]:
        """聚合数据：每个服务只保留最新的数据"""
        final_traces = []
        final_metrics = []
        final_logs = []
        
        for service in self.services:
            # 添加该服务的最新trace
            if service in self.service_traces:
                trace_data = self.service_traces[service]
                final_traces.append({
                    'trace_id': trace_data['trace_id'],
                    'spans': trace_data['spans']
                })
            
            # 添加该服务的最新metrics
            if service in self.service_metrics:
                final_metrics.extend(self.service_metrics[service]['metrics'])
            
            # 添加该服务的最新log
            if service in self.service_logs:
                final_logs.append(self.service_logs[service]['log_data'])
        
        # 返回CTH格式的数据
        result = {
            'traces': final_traces,
            'metrics': final_metrics,
            'logs': final_logs
        }
        
        print(f"\nProcessing complete:")
        print(f"- Services found: {len(self.services)} ({', '.join(sorted(self.services))})") 
        print(f"- Traces: {len(final_traces)} (one per service)")
        print(f"- Metrics: {len(final_metrics)}")
        print(f"- Logs: {len(final_logs)} (one per service)")
        
        return result


def main():
    parser = argparse.ArgumentParser(description='Convert service data to CTH format')
    parser.add_argument('files', nargs='+', help='Input JSON files')
    parser.add_argument('-o', '--output', default='cth_data.json', help='Output file path')
    parser.add_argument('--pretty', action='store_true', help='Pretty print JSON output')
    
    args = parser.parse_args()
    
    processor = DataProcessor()
    result = processor.process_files(args.files)
    
    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        if args.pretty:
            json.dump(result, f, indent=2, ensure_ascii=False)
        else:
            json.dump(result, f, ensure_ascii=False)
    
    print(f"\nOutput saved to: {args.output}")


if __name__ == '__main__':
    main()