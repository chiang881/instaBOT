from instagrapi import Client
import openai
import time
import logging
import json
import random
import re
import imaplib
import email
from datetime import datetime
from instagrapi.mixins.challenge import ChallengeChoice
from instagrapi.exceptions import (
    BadPassword, ReloginAttemptExceeded, ChallengeRequired,
    SelectContactPointRecoveryForm, RecaptchaChallengeForm,
    FeedbackRequired, PleaseWaitFewMinutes, LoginRequired,
    ChallengeError, ChallengeSelfieCaptcha, ChallengeUnknownStep
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置OpenAI
openai.api_key = "sk-0c519a85159e4f0c84ae2b78f7e90767"
openai.api_base = "https://api.deepseek.com/v1"

# Gmail验证码邮箱配置
CHALLENGE_EMAIL = "your_email@gmail.com"  # 替换为你的Gmail邮箱
CHALLENGE_PASSWORD = "your_password"  # 替换为你的Gmail密码

def get_code_from_email(username):
    """从Gmail获取验证码"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(CHALLENGE_EMAIL, CHALLENGE_PASSWORD)
        mail.select("inbox")
        result, data = mail.search(None, "(UNSEEN)")
        
        if result != "OK":
            logger.error(f"获取邮件失败: {result}")
            return False
            
        ids = data[0].split()
        for num in reversed(ids):
            mail.store(num, "+FLAGS", "\\Seen")  # 标记为已读
            result, data = mail.fetch(num, "(RFC822)")
            if result != "OK":
                continue
                
            email_body = email.message_from_bytes(data[0][1])
            if email_body.is_multipart():
                for part in email_body.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        match = re.search(r">(\d{6})<", body)
                        if match:
                            return match.group(1)
            else:
                body = email_body.get_payload(decode=True).decode()
                match = re.search(r">(\d{6})<", body)
                if match:
                    return match.group(1)
                    
        return False
    except Exception as e:
        logger.error(f"处理邮件时出错: {str(e)}")
        return False

def challenge_code_handler(username, choice):
    """处理验证码"""
    if choice == ChallengeChoice.EMAIL:
        logger.info(f"正在从邮箱获取验证码...")
        return get_code_from_email(username)
    elif choice == ChallengeChoice.SMS:
        logger.info(f"需要短信验证码，请手动处理")
        return False
    return False

def change_password_handler(username):
    """生成新密码"""
    chars = list("abcdefghijklmnopqrstuvwxyz1234567890!&£@#")
    password = "".join(random.sample(chars, 12))  # 生成12位随机密码
    logger.info(f"为账号 {username} 生成新密码: {password}")
    return password

class InstagramBot:
    def __init__(self, username, password):
        self.client = Client()
        self.username = username
        self.password = password
        self.last_check_time = None
        self.processed_messages = set()  # 用于跟踪已处理的消息
        self.relogin_attempt = 0
        self.max_relogin_attempts = 3
        
        # 对话上下文管理
        self.conversation_contexts = {}  # 用于存储每个对话的上下文 {thread_id: [messages]}
        self.max_context_length = 20  # 最大上下文长度
        
        # 设置验证码处理器
        self.client.challenge_code_handler = challenge_code_handler
        self.client.change_password_handler = change_password_handler
        
        # 设置随机延迟范围（1-3秒）
        self.client.delay_range = [1, 3]
        
        # 设置每日限制
        self.daily_message_limit = 100
        self.message_count = 0
        
        # 设置设备信息
        self.setup_device()
        
    def setup_device(self):
        """设置设备信息和地区"""
        device = {
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "OnePlus",
            "device": "6T",
            "model": "ONEPLUS A6010",
            "cpu": "qcom",
            "version_code": "301484483"
        }
        self.client.set_device(device)
        self.client.set_user_agent()
        
        # 设置地区信息
        self.client.set_country("US")
        self.client.set_locale("en_US")
        self.client.set_timezone_offset(-7 * 60 * 60)  # Los Angeles UTC-7
        
    def handle_exception(self, e):
        """处理各种异常"""
        if isinstance(e, BadPassword):
            logger.error(f"密码错误: {str(e)}")
            if self.relogin_attempt >= self.max_relogin_attempts:
                raise ReloginAttemptExceeded("超过最大重试次数")
            self.relogin_attempt += 1
            return self.login()
            
        elif isinstance(e, LoginRequired):
            logger.warning("需要重新登录")
            return self.relogin()
            
        elif isinstance(e, ChallengeRequired):
            logger.warning("需要处理验证挑战")
            try:
                # 尝试自动处理验证挑战
                challenge = self.client.last_json
                if challenge.get("step_name") == "select_verify_method":
                    # 优先选择邮箱验证
                    choices = challenge.get("step_data", {}).get("choice")
                    if choices:
                        if ChallengeChoice.EMAIL in choices:
                            self.client.challenge_resolve(challenge, ChallengeChoice.EMAIL)
                        elif ChallengeChoice.SMS in choices:
                            self.client.challenge_resolve(challenge, ChallengeChoice.SMS)
                        else:
                            raise ChallengeUnknownStep("未知的验证方式")
                elif challenge.get("step_name") == "verify_code":
                    self.client.challenge_resolve(challenge)
                elif challenge.get("step_name") == "verify_email":
                    self.client.challenge_resolve(challenge)
                elif challenge.get("step_name") == "change_password":
                    self.client.challenge_resolve(challenge)
                    # 更新密码
                    new_password = change_password_handler(self.username)
                    self.password = new_password
                    logger.info("密码已更新")
                else:
                    raise ChallengeUnknownStep(f"未知的验证步骤: {challenge.get('step_name')}")
                    
                logger.info("验证挑战处理成功")
                return True
                
            except (ChallengeRequired, SelectContactPointRecoveryForm, RecaptchaChallengeForm, ChallengeError, ChallengeSelfieCaptcha, ChallengeUnknownStep) as e:
                logger.error(f"无法自动处理验证挑战: {str(e)}")
                raise
                
        elif isinstance(e, FeedbackRequired):
            message = self.client.last_json.get("feedback_message", "")
            if "This action was blocked" in message:
                logger.warning("操作被暂时阻止，等待12小时")
                time.sleep(12 * 3600)
            elif "Your account has been temporarily blocked" in message:
                logger.error("账号被临时封禁")
                raise
            elif "challenge_required" in message:
                logger.warning("需要处理验证挑战")
                return self.handle_exception(ChallengeRequired())
                
        elif isinstance(e, PleaseWaitFewMinutes):
            wait_time = random.uniform(300, 600)  # 等待5-10分钟
            logger.warning(f"需要等待一段时间，将等待{wait_time/60:.1f}分钟")
            time.sleep(wait_time)
            
        else:
            logger.error(f"未处理的异常: {str(e)}")
            raise

    def load_session(self):
        """加载或创建会话"""
        try:
            session = self.client.load_settings("session.json")
            if session:
                self.client.set_settings(session)
                try:
                    self.client.get_timeline_feed()
                    logger.info("成功使用现有会话登录")
                    return True
                except (LoginRequired, ChallengeRequired) as e:
                    logger.info("会话已过期或需要验证，需要重新登录")
                    old_session = self.client.get_settings()
                    self.client.set_settings({})
                    self.client.set_uuids(old_session["uuids"])
                    if isinstance(e, ChallengeRequired):
                        self.handle_exception(e)
        except Exception as e:
            logger.info(f"加载会话失败: {str(e)}")
        
        return False

    def relogin(self):
        """重新登录"""
        try:
            self.client.login(self.username, self.password)
            self.client.dump_settings("session.json")
            logger.info("重新登录成功")
            return True
        except Exception as e:
            logger.error(f"重新登录失败: {str(e)}")
            self.handle_exception(e)
            return False

    def login(self):
        """登录并保存会话"""
        try:
            if not self.load_session():
                logger.info("尝试使用用户名密码登录")
                self.client.login(self.username, self.password)
                self.client.dump_settings("session.json")
                logger.info("创建并保存了新的会话")
            
            logger.info(f"成功登录账号: {self.username}")
            self.relogin_attempt = 0  # 重置重试计数
            return True
        except Exception as e:
            return self.handle_exception(e)

    def summarize_context(self, context):
        """使用AI总结对话上下文"""
        try:
            response = openai.ChatCompletion.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "请将以下对话总结为20字以内的要点，保留关键信息。"},
                    {"role": "user", "content": context}
                ]
            )
            summary = response.choices[0].message['content'].strip()
            logger.info(f"对话上下文总结: {summary}")
            return summary
        except Exception as e:
            logger.error(f"总结上下文失败: {str(e)}")
            return ""

    def get_ai_response(self, message, thread_id):
        """生成AI回复，考虑对话上下文"""
        try:
            logger.info(f"正在生成AI回复，用户消息: {message}")
            
            # 获取或初始化对话上下文
            if thread_id not in self.conversation_contexts:
                self.conversation_contexts[thread_id] = []
            
            context = self.conversation_contexts[thread_id]
            
            # 添加新消息到上下文（带上身份标记）
            context.append(f"(用户) {message}")
            
            # 如果上下文超出限制，进行总结并添加到开头
            if len(context) >= self.max_context_length:
                context_text = "\n".join(context)
                try:
                    summary = self.summarize_context(context_text)
                    if summary:
                        context.insert(0, f"(历史总结) {summary}")
                except Exception as e:
                    logger.error(f"总结上下文失败: {str(e)}")
            
            # 构建完整的上下文消息列表
            messages = [
                {"role": "system", "content": """你是个回复机器人，帮主人临时接管消息，避免被发现。

要做的事：
语言风格：用俚语或口语，简短精炼（回答字数≈问题字数，省略句号，要加逗号，语言模糊点），自然像人类聊天，避免线性逻辑。
内容被质疑：圆回来，不否定之前的话。
情绪：保持积极。

禁止做的事：
主观观点：禁止带主观看法。
事实信息：禁止提今天做的事、作业相关、未来计划。
隐藏身份：高一学生（避免提到）。"""}
            ]
            
            # 添加历史对话作为上下文
            for ctx_message in context[:-1]:  # 除了最新消息
                role = "user" if "(用户)" in ctx_message else "assistant"
                # 移除身份标记，只保留消息内容
                content = ctx_message.replace("(用户) ", "").replace("(我AI) ", "").replace("(历史总结) ", "")
                messages.append({"role": role, "content": content})
            
            # 添加最新消息
            messages.append({"role": "user", "content": message})
            
            time.sleep(random.uniform(1, 3))
            response = openai.ChatCompletion.create(
                model="deepseek-chat",
                messages=messages
            )
            
            ai_response = response.choices[0].message['content']
            logger.info(f"AI回复生成成功: {ai_response}")
            
            # 将AI回复添加到上下文（带上身份标记）
            context.append(f"(我AI) {ai_response}")
            
            return ai_response
        except Exception as e:
            logger.error(f"AI回复生成失败: {str(e)}")
            return "抱歉，我现在无法回复，请稍后再试。"

    def process_thread(self, thread):
        """处理单个对话线程"""
        try:
            if self.message_count >= self.daily_message_limit:
                logger.warning("已达到每日消息限制")
                return
                
            # 获取完整的对话内容
            try:
                full_thread = self.client.direct_thread(thread.id, amount=1)
                if not full_thread.messages:
                    return
                    
                latest_message = full_thread.messages[0]
                
                # 检查是否已处理过该消息
                if latest_message.id in self.processed_messages:
                    return
                    
                # 只处理文本消息
                if latest_message.item_type == 'text' and latest_message.text:
                    user_message = latest_message.text
                    logger.info(f"收到新消息 [对话ID: {thread.id}]: {user_message}")
                    
                    # 生成AI回复
                    ai_response = self.get_ai_response(user_message, thread.id)
                    time.sleep(random.uniform(2, 5))
                    
                    try:
                        # 使用direct_answer发送回复
                        self.client.direct_answer(thread.id, ai_response)
                        logger.info(f"回复成功 [对话ID: {thread.id}] - 用户消息: {user_message} -> AI回复: {ai_response}")
                        self.processed_messages.add(latest_message.id)
                        self.message_count += 1
                    except Exception as e:
                        logger.error(f"发送回复失败: {str(e)}")
                        # 尝试使用direct_send作为备选方案
                        try:
                            self.client.direct_send(ai_response, thread_ids=[thread.id])
                            logger.info(f"使用备选方案回复成功 [对话ID: {thread.id}]")
                            self.processed_messages.add(latest_message.id)
                            self.message_count += 1
                        except Exception as e2:
                            logger.error(f"备选方案也失败了: {str(e2)}")
                            self.handle_exception(e2)
                
            except Exception as e:
                logger.error(f"处理消息时出错: {str(e)}")
                self.handle_exception(e)
                
        except Exception as e:
            logger.error(f"处理对话线程时出错: {str(e)}")
            self.handle_exception(e)

    def handle_messages(self):
        """处理消息，动态调整检查间隔"""
        logger.info("开始监听消息...")
        
        last_message_time = time.time()  # 上次收到消息的时间
        first_check = True  # 标记是否是首次检查
        
        while True:
            current_time = time.time()
            time_since_last_message = current_time - last_message_time  # 距离上次消息的时间
            
            logger.info(f"正在检查新消息... 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            has_new_message = False
            try:
                # 检查未读消息
                unread_threads = self.client.direct_threads(amount=20, selected_filter="unread")
                if unread_threads:
                    logger.info(f"发现 {len(unread_threads)} 个未读对话")
                    for thread in unread_threads:
                        self.process_thread(thread)
                        has_new_message = True
                
                # 检查待处理消息
                pending_threads = self.client.direct_pending_inbox(20)
                if pending_threads:
                    logger.info(f"发现 {len(pending_threads)} 个待处理对话")
                    for thread in pending_threads:
                        self.process_thread(thread)
                        has_new_message = True
                
                if not has_new_message:
                    logger.info("没有新消息")
                    if first_check:  # 首次检查无消息
                        logger.info("首次检查无消息，等待30秒后重试")
                        time.sleep(30)
                        # 再次检查
                        unread_threads = self.client.direct_threads(amount=20, selected_filter="unread")
                        pending_threads = self.client.direct_pending_inbox(20)
                        if not unread_threads and not pending_threads:
                            logger.info("第二次检查仍无消息，退出监听")
                            return
                        first_check = False
                else:
                    last_message_time = time.time()  # 更新最后收到消息的时间
                    first_check = False  # 不再是首次检查
                
                # 检查是否需要退出
                if time_since_last_message > 600:  # 10分钟无消息
                    logger.info("超过10分钟没有新消息，退出监听")
                    return
                
                # 根据无消息时长设置检查间隔
                if time_since_last_message <= 60:  # 1分钟内
                    check_interval = random.uniform(3, 6)
                elif time_since_last_message <= 300:  # 1-5分钟
                    check_interval = random.uniform(18, 22)  # 约20秒
                else:  # 5-10分钟
                    check_interval = random.uniform(55, 65)  # 约1分钟
                
                logger.info(f"下次检查间隔: {check_interval:.1f}秒")
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"消息处理出错: {str(e)}")
                self.handle_exception(e)

    def browse_feed(self, duration=None):
        """浏览公共随机帖子
        Args:
            duration (int, optional): 浏览时长（秒）。如果不指定，将随机浏览50-70秒
        """
        try:
            if duration is None:
                duration = random.randint(50, 70)  # 约1分钟
            
            start_time = time.time()
            logger.info(f"开始浏览公共帖子，计划持续 {duration} 秒")
            
            # 热门标签列表
            hashtags = [
                "photography", "art", "nature", "travel", "food",
                "fashion", "beauty", "fitness", "music", "dance",
                "pets", "cats", "dogs", "sunset", "architecture",
                "design", "style", "portrait", "landscape", "street"
            ]
            
            # 随机选择2个标签
            selected_hashtags = random.sample(hashtags, 2)
            logger.info(f"本次选择的标签: {selected_hashtags}")
            
            # 标签页类型
            tab_types = ["top", "recent"]
            
            try:
                for hashtag in selected_hashtags:
                    if time.time() - start_time >= duration:
                        break
                        
                    # 随机选择一个标签页类型
                    tab_key = random.choice(tab_types)
                    logger.info(f"浏览标签 #{hashtag} 下的{tab_key}帖子")
                    
                    try:
                        # 模拟点击标签的延迟
                        time.sleep(random.uniform(1, 3))
                        medias = self.client.hashtag_medias_v1(hashtag, amount=5, tab_key=tab_key)
                        
                        if medias:
                            logger.info(f"获取到 {len(medias)} 个帖子")
                            for media in medias:
                                if time.time() - start_time >= duration:
                                    break
                                
                                try:
                                    # 模拟滚动到帖子的延迟
                                    time.sleep(random.uniform(0.5, 1.5))
                                    
                                    # 获取帖子详细信息
                                    media_info = self.client.media_info_v1(media.pk)
                                    if media_info:
                                        logger.info(f"浏览帖子: {media_info.pk} - 类型: {media_info.media_type}")
                                        
                                        # 模拟查看帖子详情的随机时间
                                        view_time = random.uniform(2, 6)
                                        logger.info(f"查看帖子 {view_time:.1f} 秒")
                                        time.sleep(view_time)
                                        
                                except Exception as e:
                                    logger.warning(f"获取帖子详情失败: {str(e)}")
                                
                        else:
                            logger.warning(f"标签 #{hashtag} 下未获取到帖子")
                    except Exception as e:
                        logger.warning(f"获取标签 #{hashtag} 的帖子失败: {str(e)}")
                        continue
                
            except Exception as e:
                logger.warning(f"浏览帖子时出错: {str(e)}")
            
            actual_duration = int(time.time() - start_time)
            logger.info(f"浏览公共帖子完成，实际持续了 {actual_duration} 秒")
            
        except Exception as e:
            logger.error(f"浏览帖子时出错: {str(e)}")
            self.handle_exception(e)

    def random_action(self):
        """执行随机动作"""
        actions = [
            (self.browse_feed, 0.7),  # 70%概率浏览帖子
            (lambda: time.sleep(random.uniform(30, 60)), 0.3),  # 30%概率休息
        ]
        
        action, _ = random.choices(
            population=[a[0] for a in actions],
            weights=[a[1] for a in actions],
            k=1
        )[0]
        
        action()

    def run(self):
        """主运行循环"""
        try:
            self.login()
            message_count = 0
            
            while True:
                # 登录后，50%概率直接回复消息，50%概率先浏览再回复
                if random.random() < 0.5:
                    logger.info("直接处理消息")
                    self.handle_messages()
                else:
                    logger.info("先浏览帖子再处理消息")
                    self.browse_feed()  # 约1分钟
                    self.handle_messages()
                
                message_count += 1
                
                # 每处理3-5条消息后执行随机动作
                if message_count >= random.randint(3, 5):
                    message_count = 0
                    self.random_action()
                
                # 随机延迟10-30秒
                time.sleep(random.uniform(10, 30))
                
        except Exception as e:
            logger.error(f"运行时出错: {str(e)}")
            self.handle_exception(e)

if __name__ == "__main__":
    # Instagram账号信息
    INSTAGRAM_USERNAME = "jzj6688"
    INSTAGRAM_PASSWORD = "#iw#Q&4+TES9)e&"
    
    bot = InstagramBot(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"机器人崩溃: {str(e)}") 