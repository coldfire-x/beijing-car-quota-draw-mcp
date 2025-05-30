"""
北京汽车摇号数据分析模块
提供摇号成功率、等待时长、趋势分析等功能
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LotteryAnalyzer:
    """北京汽车摇号数据分析器"""
    
    def __init__(self, data_store):
        self.data_store = data_store
    
    async def get_comprehensive_analysis(self) -> Dict[str, Any]:
        """获取全面的分析报告"""
        try:
            # 获取基础统计
            stats = await self.data_store.get_statistics()
            
            # 按年份分类数据
            years_data = self._categorize_files_by_year(stats)
            
            # 计算成功率
            success_rates = self._calculate_success_rates(years_data)
            
            # 估算等待时长
            waiting_analysis = self._estimate_waiting_time(years_data)
            
            # 趋势分析
            trends = self._analyze_trends(success_rates)
            
            # 生成建议
            recommendations = self._generate_recommendations(success_rates, waiting_analysis)
            
            return {
                "overview": {
                    "total_files": stats.get("total_files", 0),
                    "total_entries": stats.get("total_entries", 0),
                    "application_codes_indexed": stats.get("application_codes_indexed", 0),
                    "id_numbers_indexed": stats.get("id_numbers_indexed", 0),
                    "last_update": stats.get("last_update", ""),
                    "analysis_timestamp": datetime.now().isoformat()
                },
                "years_data": years_data,
                "success_rates": success_rates,
                "waiting_analysis": waiting_analysis,
                "trends": trends,
                "recommendations": recommendations
            }
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            raise
    
    async def get_success_rates(self) -> Dict[str, Any]:
        """获取摇号成功率分析"""
        try:
            stats = await self.data_store.get_statistics()
            years_data = self._categorize_files_by_year(stats)
            success_rates = self._calculate_success_rates(years_data)
            
            return {
                "analysis_type": "success_rates",
                "timestamp": datetime.now().isoformat(),
                "success_rates": success_rates
            }
        except Exception as e:
            logger.error(f"Error calculating success rates: {e}")
            raise
    
    async def get_waiting_time_analysis(self) -> Dict[str, Any]:
        """获取等待时长分析"""
        try:
            stats = await self.data_store.get_statistics()
            years_data = self._categorize_files_by_year(stats)
            waiting_analysis = self._estimate_waiting_time(years_data)
            
            return {
                "analysis_type": "waiting_time",
                "timestamp": datetime.now().isoformat(),
                "waiting_analysis": waiting_analysis
            }
        except Exception as e:
            logger.error(f"Error analyzing waiting time: {e}")
            raise
    
    async def get_trend_analysis(self) -> Dict[str, Any]:
        """获取趋势分析"""
        try:
            stats = await self.data_store.get_statistics()
            years_data = self._categorize_files_by_year(stats)
            success_rates = self._calculate_success_rates(years_data)
            trends = self._analyze_trends(success_rates)
            
            return {
                "analysis_type": "trends",
                "timestamp": datetime.now().isoformat(),
                "trends": trends
            }
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            raise
    
    def _categorize_files_by_year(self, stats: Dict[str, Any]) -> Dict[str, Dict]:
        """按年份分类文件"""
        years_data = {}
        
        for file_info in stats.get('files', []):
            year = self._extract_year(file_info)
            
            if year not in years_data:
                years_data[year] = {'winners': [], 'waiting': []}
            
            if file_info['type'] == 'score_ranking':
                years_data[year]['winners'].append(file_info)
            elif file_info['type'] == 'waiting_list':
                years_data[year]['waiting'].append(file_info)
        
        return years_data
    
    def _extract_year(self, file_info: Dict) -> str:
        """从文件信息中提取年份"""
        # 尝试从source_url提取
        url = file_info.get('source_url', '')
        if '2024' in url:
            return '2024'
        elif '2025' in url:
            return '2025'
        elif '2023' in url:
            return '2023'
        elif '2022' in url:
            return '2022'
        
        # 尝试从下载时间提取
        download_time = file_info.get('download_time', '')
        if download_time:
            try:
                dt = datetime.fromisoformat(download_time.replace('Z', '+00:00'))
                return str(dt.year)
            except:
                pass
        
        return 'unknown'
    
    def _calculate_success_rates(self, years_data: Dict[str, Dict]) -> Dict[str, Any]:
        """计算各年份摇号成功率"""
        success_rates = {}
        
        for year, data in years_data.items():
            if year == 'unknown':
                continue
            
            total_winners = sum(f['entries'] for f in data['winners'])
            total_waiting = sum(f['entries'] for f in data['waiting'])
            
            # 估算申请总数
            # 基于历史数据，未中签未排队的人数通常是中签人数的15-20倍
            estimated_applicants = total_winners * 18 + total_waiting
            
            success_rate = (total_winners / estimated_applicants) * 100 if estimated_applicants > 0 else 0
            waiting_rate = (total_waiting / estimated_applicants) * 100 if estimated_applicants > 0 else 0
            
            success_rates[year] = {
                'year': year,
                'winners': total_winners,
                'waiting': total_waiting,
                'estimated_applicants': estimated_applicants,
                'success_rate': round(success_rate, 4),
                'waiting_rate': round(waiting_rate, 2),
                'rejection_rate': round(100 - success_rate - waiting_rate, 2),
                'winner_files': len(data['winners']),
                'waiting_files': len(data['waiting'])
            }
        
        return success_rates
    
    def _estimate_waiting_time(self, years_data: Dict[str, Dict]) -> Dict[str, Any]:
        """估算排队等待时长"""
        waiting_analysis = {}
        
        for year, data in years_data.items():
            if year == 'unknown':
                continue
            
            total_waiting = sum(f['entries'] for f in data['waiting'])
            total_winners = sum(f['entries'] for f in data['winners'])
            
            # 基于历史数据估算年度配额
            annual_quota = total_winners if total_winners > 0 else 50000
            
            # 估算平均等待时间
            if total_waiting > 0:
                avg_waiting_years = total_waiting / annual_quota
                avg_waiting_months = avg_waiting_years * 12
            else:
                avg_waiting_years = 0
                avg_waiting_months = 0
            
            waiting_analysis[year] = {
                'year': year,
                'waiting_count': total_waiting,
                'annual_quota': annual_quota,
                'avg_waiting_years': round(avg_waiting_years, 1),
                'avg_waiting_months': round(avg_waiting_months, 1),
                'queue_status': self._get_queue_status(avg_waiting_years)
            }
        
        return waiting_analysis
    
    def _get_queue_status(self, waiting_years: float) -> str:
        """根据等待年数判断排队状态"""
        if waiting_years < 1:
            return "短期等待"
        elif waiting_years < 3:
            return "中期等待"
        elif waiting_years < 5:
            return "长期等待"
        else:
            return "超长期等待"
    
    def _analyze_trends(self, success_rates: Dict[str, Any]) -> Dict[str, Any]:
        """分析趋势变化"""
        if len(success_rates) < 2:
            return {"message": "需要至少两年的数据才能进行趋势分析"}
        
        years = sorted(success_rates.keys())
        latest_year = years[-1]
        previous_year = years[-2]
        
        success_change = (success_rates[latest_year]['success_rate'] - 
                         success_rates[previous_year]['success_rate'])
        
        waiting_change = (success_rates[latest_year]['waiting'] - 
                         success_rates[previous_year]['waiting'])
        
        return {
            'years_analyzed': years,
            'latest_year': latest_year,
            'previous_year': previous_year,
            'success_rate_change': round(success_change, 4),
            'waiting_count_change': waiting_change,
            'trend_direction': '上升' if success_change > 0 else '下降' if success_change < 0 else '稳定',
            'competition_level': '加剧' if success_change < 0 else '缓解' if success_change > 0 else '稳定',
            'analysis': self._get_trend_analysis_text(success_change, waiting_change)
        }
    
    def _get_trend_analysis_text(self, success_change: float, waiting_change: int) -> str:
        """生成趋势分析文本"""
        analysis = []
        
        if success_change > 0:
            analysis.append("摇号成功率有所提升")
        elif success_change < 0:
            analysis.append("摇号成功率有所下降")
        else:
            analysis.append("摇号成功率保持稳定")
        
        if waiting_change > 0:
            analysis.append("排队人数增加")
        elif waiting_change < 0:
            analysis.append("排队人数减少")
        else:
            analysis.append("排队人数基本稳定")
        
        return "，".join(analysis)
    
    def _generate_recommendations(self, success_rates: Dict[str, Any], 
                                waiting_analysis: Dict[str, Any]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if not success_rates:
            return ["数据不足，无法生成建议"]
        
        # 获取最新年份的数据
        latest_year = max(success_rates.keys())
        latest_stats = success_rates[latest_year]
        latest_waiting = waiting_analysis.get(latest_year, {})
        
        success_rate = latest_stats.get('success_rate', 0)
        avg_waiting_years = latest_waiting.get('avg_waiting_years', 0)
        
        # 基于成功率的建议
        if success_rate < 0.1:
            recommendations.append("摇号成功率极低，建议考虑新能源车型或家庭摇号")
        elif success_rate < 0.5:
            recommendations.append("摇号成功率较低，建议长期准备或考虑其他方案")
        else:
            recommendations.append("摇号成功率相对较高，可以继续参与")
        
        # 基于等待时间的建议
        if avg_waiting_years > 5:
            recommendations.append("排队等待时间很长，建议考虑新能源车型")
        elif avg_waiting_years > 2:
            recommendations.append("排队等待时间较长，建议做好长期准备")
        else:
            recommendations.append("排队等待时间相对较短")
        
        # 通用建议
        recommendations.extend([
            "建议关注政策变化，及时调整策略",
            "可考虑家庭摇号以提高中签概率",
            "新能源车型配额相对充足，值得考虑"
        ])
        
        return recommendations 