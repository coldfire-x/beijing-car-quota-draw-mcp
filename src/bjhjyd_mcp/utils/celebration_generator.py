"""
Celebration HTML generator for lottery winners.

Generates beautiful HTML pages with splash effects and animations
to celebrate users who have won the car quota lottery.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class CelebrationGenerator:
    """Generates celebration HTML pages for lottery winners."""
    
    def __init__(self):
        """Initialize the celebration generator."""
        self.templates_dir = Path(__file__).parent / "templates"
        self.templates_dir.mkdir(exist_ok=True)
    
    def generate_celebration_page(
        self,
        winner_info: Dict[str, Any],
        lottery_results: List[Dict[str, Any]],
        save_path: Optional[Path] = None
    ) -> str:
        """
        Generate a celebration HTML page for a lottery winner.
        
        Args:
            winner_info: Information about the winner (application code, name, etc.)
            lottery_results: List of lottery results for this winner
            save_path: Optional path to save the HTML file
            
        Returns:
            HTML content as string
        """
        # Extract winner details
        application_code = winner_info.get("application_code", "")
        name = winner_info.get("name", "恭喜您")
        id_info = winner_info.get("id_info", "")
        
        # Determine lottery type and details
        lottery_type = self._determine_lottery_type(lottery_results)
        lottery_details = self._extract_lottery_details(lottery_results)
        
        # Generate HTML content
        html_content = self._create_html_template(
            application_code=application_code,
            name=name,
            id_info=id_info,
            lottery_type=lottery_type,
            lottery_details=lottery_details
        )
        
        # Save to file if path provided
        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        
        return html_content
    
    def _determine_lottery_type(self, lottery_results: List[Dict[str, Any]]) -> str:
        """Determine the type of lottery based on results."""
        if not lottery_results:
            return "新能源小客车指标"
        
        # Check the source file or type to determine lottery category
        first_result = lottery_results[0]
        source_url = first_result.get("source_url", "").lower()
        
        if "家庭" in source_url or "family" in source_url.lower():
            return "家庭新能源小客车指标"
        elif "单位" in source_url or "unit" in source_url.lower():
            return "单位新能源小客车指标"
        else:
            return "个人新能源小客车指标"
    
    def _extract_lottery_details(self, lottery_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract relevant details from lottery results."""
        if not lottery_results:
            return {}
        
        latest_result = lottery_results[0]  # Assume first is most recent
        
        return {
            "sequence_number": latest_result.get("sequence_number"),
            "waiting_time": latest_result.get("waiting_time"),
            "source_file": latest_result.get("source_file"),
            "download_time": latest_result.get("download_time"),
            "total_results": len(lottery_results)
        }
    
    def _create_html_template(
        self,
        application_code: str,
        name: str,
        id_info: str,
        lottery_type: str,
        lottery_details: Dict[str, Any]
    ) -> str:
        """Create the HTML template with celebration effects."""
        
        # Generate random celebration messages
        celebration_messages = [
            "🎉 恭喜您！中签了！🎉",
            "🚗 您的新能源车梦想成真了！🚗",
            "🌟 幸运降临！您获得了车牌指标！🌟",
            "🎊 太棒了！您在摇号中获胜！🎊",
            "✨ 好运连连！车牌指标属于您了！✨"
        ]
        
        main_message = random.choice(celebration_messages)
        
        # Format date
        current_date = datetime.now().strftime("%Y年%m月%d日")
        
        # Create sharing messages
        sharing_messages = [
            f"我在北京新能源车摇号中中签了！申请编码：{application_code}",
            f"好消息！我获得了{lottery_type}！",
            f"经过漫长等待，终于中签了！{lottery_type}到手！",
            f"分享一个好消息：我的{lottery_type}申请成功了！"
        ]
        
        share_text = random.choice(sharing_messages)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎉 中签庆祝 - {name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }}
        
        /* Celebration animations */
        .firework {{
            position: absolute;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            animation: firework 2s ease-out infinite;
        }}
        
        @keyframes firework {{
            0% {{
                opacity: 1;
                transform: scale(0) translateY(0);
            }}
            50% {{
                opacity: 1;
                transform: scale(1) translateY(-100px);
            }}
            100% {{
                opacity: 0;
                transform: scale(0) translateY(-200px);
            }}
        }}
        
        .confetti {{
            position: absolute;
            width: 8px;
            height: 8px;
            background: #ff6b6b;
            animation: confetti 3s ease-in-out infinite;
        }}
        
        @keyframes confetti {{
            0% {{
                transform: translateY(-100vh) rotate(0deg);
                opacity: 1;
            }}
            100% {{
                transform: translateY(100vh) rotate(720deg);
                opacity: 0;
            }}
        }}
        
        .sparkle {{
            position: absolute;
            width: 4px;
            height: 4px;
            background: #ffd700;
            border-radius: 50%;
            animation: sparkle 1.5s ease-in-out infinite;
        }}
        
        @keyframes sparkle {{
            0%, 100% {{
                opacity: 0;
                transform: scale(0);
            }}
            50% {{
                opacity: 1;
                transform: scale(1);
            }}
        }}
        
        /* Main content */
        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            text-align: center;
            position: relative;
            z-index: 10;
        }}
        
        .celebration-card {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 3rem 2rem;
            margin: 2rem 0;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            animation: cardAppear 0.8s ease-out;
        }}
        
        @keyframes cardAppear {{
            from {{
                opacity: 0;
                transform: translateY(50px) scale(0.9);
            }}
            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
            }}
        }}
        
        .main-title {{
            font-size: 2.5rem;
            color: #2c3e50;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
            animation: pulse 2s ease-in-out infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{
                transform: scale(1);
            }}
            50% {{
                transform: scale(1.05);
            }}
        }}
        
        .lottery-type {{
            font-size: 1.5rem;
            color: #8e44ad;
            margin-bottom: 2rem;
            font-weight: 600;
        }}
        
        .details-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin: 2rem 0;
        }}
        
        .detail-card {{
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 15px;
            padding: 1.5rem;
            border: 2px solid #dee2e6;
            transition: transform 0.3s ease;
        }}
        
        .detail-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
        }}
        
        .detail-label {{
            font-size: 0.9rem;
            color: #6c757d;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }}
        
        .detail-value {{
            font-size: 1.2rem;
            color: #2c3e50;
            font-weight: 600;
        }}
        
        .action-buttons {{
            margin-top: 3rem;
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
        }}
        
        .btn {{
            padding: 12px 30px;
            border: none;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }}
        
        .btn-primary {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }}
        
        .btn-secondary {{
            background: linear-gradient(135deg, #ffecd2, #fcb69f);
            color: #8e44ad;
        }}
        
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
        }}
        
        .footer {{
            margin-top: 3rem;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9rem;
        }}
        
        /* Responsive design */
        @media (max-width: 600px) {{
            .container {{
                padding: 1rem;
            }}
            
            .main-title {{
                font-size: 2rem;
            }}
            
            .details-grid {{
                grid-template-columns: 1fr;
            }}
            
            .action-buttons {{
                flex-direction: column;
                align-items: center;
            }}
        }}
    </style>
</head>
<body>
    <!-- Celebration effects -->
    <div id="celebration-effects"></div>
    
    <div class="container">
        <div class="celebration-card">
            <h1 class="main-title">{main_message}</h1>
            <div class="lottery-type">{lottery_type}</div>
            
            <div class="details-grid">
                <div class="detail-card">
                    <div class="detail-label">申请编码</div>
                    <div class="detail-value">{application_code}</div>
                </div>
                
                <div class="detail-card">
                    <div class="detail-label">中签日期</div>
                    <div class="detail-value">{current_date}</div>
                </div>
                
                {f'''
                <div class="detail-card">
                    <div class="detail-label">序号</div>
                    <div class="detail-value">{lottery_details.get("sequence_number", "N/A")}</div>
                </div>
                ''' if lottery_details.get("sequence_number") else ""}
                
                {f'''
                <div class="detail-card">
                    <div class="detail-label">排队时间</div>
                    <div class="detail-value">{lottery_details.get("waiting_time", "N/A")[:10] if lottery_details.get("waiting_time") else "N/A"}</div>
                </div>
                ''' if lottery_details.get("waiting_time") else ""}
            </div>
            
            <div class="action-buttons">
                <button class="btn btn-primary" onclick="shareNews()">
                    📱 分享好消息
                </button>
                <button class="btn btn-secondary" onclick="downloadPage()">
                    💾 保存纪念页
                </button>
                <button class="btn btn-secondary" onclick="printPage()">
                    🖨️ 打印纪念
                </button>
            </div>
        </div>
        
        <div class="footer">
            <p>🎊 祝贺您获得北京新能源小客车指标！🎊</p>
            <p>请及时关注后续购车和上牌流程</p>
        </div>
    </div>
    
    <script>
        // Create celebration effects
        function createCelebrationEffects() {{
            const effectsContainer = document.getElementById('celebration-effects');
            
            // Create fireworks
            for (let i = 0; i < 20; i++) {{
                const firework = document.createElement('div');
                firework.className = 'firework';
                firework.style.left = Math.random() * 100 + '%';
                firework.style.background = `hsl(${{Math.random() * 360}}, 70%, 60%)`;
                firework.style.animationDelay = Math.random() * 2 + 's';
                effectsContainer.appendChild(firework);
            }}
            
            // Create confetti
            for (let i = 0; i < 30; i++) {{
                const confetti = document.createElement('div');
                confetti.className = 'confetti';
                confetti.style.left = Math.random() * 100 + '%';
                confetti.style.background = `hsl(${{Math.random() * 360}}, 70%, 60%)`;
                confetti.style.animationDelay = Math.random() * 3 + 's';
                confetti.style.animationDuration = (Math.random() * 2 + 2) + 's';
                effectsContainer.appendChild(confetti);
            }}
            
            // Create sparkles
            for (let i = 0; i < 50; i++) {{
                const sparkle = document.createElement('div');
                sparkle.className = 'sparkle';
                sparkle.style.left = Math.random() * 100 + '%';
                sparkle.style.top = Math.random() * 100 + '%';
                sparkle.style.animationDelay = Math.random() * 1.5 + 's';
                effectsContainer.appendChild(sparkle);
            }}
        }}
        
        // Share functionality
        function shareNews() {{
            const shareText = "{share_text}";
            
            if (navigator.share) {{
                navigator.share({{
                    title: '🎉 北京车牌中签啦！',
                    text: shareText,
                    url: window.location.href
                }});
            }} else {{
                // Fallback - copy to clipboard
                navigator.clipboard.writeText(shareText).then(() => {{
                    alert('好消息已复制到剪贴板！快去分享吧！');
                }});
            }}
        }}
        
        // Download page as image (simplified)
        function downloadPage() {{
            window.print();
        }}
        
        // Print page
        function printPage() {{
            window.print();
        }}
        
        // Add sound effect (optional)
        function playSuccessSound() {{
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwbCy3BxuPzgl0gGJPXy+iKUB8aN');
            audio.play().catch(() => {{}}); // Ignore errors
        }}
        
        // Initialize effects when page loads
        document.addEventListener('DOMContentLoaded', function() {{
            createCelebrationEffects();
            playSuccessSound();
            
            // Add additional effects after a delay
            setTimeout(() => {{
                document.querySelector('.celebration-card').style.transform = 'scale(1.02)';
                setTimeout(() => {{
                    document.querySelector('.celebration-card').style.transform = 'scale(1)';
                }}, 200);
            }}, 1000);
        }});
    </script>
</body>
</html>
        """
        
        return html_content
    
    def create_sharing_links(self, winner_info: Dict[str, Any]) -> Dict[str, str]:
        """Create social media sharing links."""
        application_code = winner_info.get("application_code", "")
        share_text = f"我在北京新能源车摇号中中签了！申请编码：{application_code}"
        
        return {
            "wechat": f"weixin://",  # WeChat sharing requires special handling
            "weibo": f"https://service.weibo.com/share/share.php?title={share_text}",
            "qq": f"https://connect.qq.com/widget/shareqq/index.html?title={share_text}",
            "copy": share_text
        } 