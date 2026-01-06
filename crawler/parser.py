import httpx
from bs4 import BeautifulSoup
from config import Config
import json

class QuestionParser:
    """题目解析器，用于解析题目HTML并提取相关信息"""
    
    def __init__(self):
        self.config = Config()
    
    def parse_question_from_html(self, html_content):
        """
        从HTML内容中解析题目信息
        :param html_content: 题目HTML内容
        :return: 解析后的题目信息字典
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取题目信息
        question_card = soup.find('div', class_='question-card')
        if not question_card:
            return None
        
        # 题目类型
        question_type_element = question_card.find('span', class_='question-type')
        question_type = question_type_element.get_text(strip=True) if question_type_element else ""
        
        # 题目内容
        question_text_element = question_card.find('div', class_='question-text')
        question_text = question_text_element.get_text(strip=True) if question_text_element else ""
        
        # 选项
        options_data = {}
        options_container = question_card.find('div', class_='optionsContainer')
        if options_container:
            # 尝试从data-options属性获取选项
            data_options = options_container.get('data-options')
            if data_options:
                try:
                    # 替换&quot;为"，然后解析JSON
                    cleaned_data_options = str(data_options).replace('&quot;', '"')
                    options_data = json.loads(cleaned_data_options)
                except json.JSONDecodeError:
                    # 如果data-options解析失败，则从HTML元素获取选项
                    option_items = options_container.find_all('div', class_='option-item')
                    for item in option_items:
                        label_element = item.find('span', class_='option-label')
                        label = label_element.get_text(strip=True).rstrip(':') if label_element else ""
                        text = item.get_text(strip=True)[3:] if item.get_text() else ""
                        options_data[label] = text
            else:
                # 从HTML元素获取选项
                option_items = options_container.find_all('div', class_='option-item')
                for item in option_items:
                    label_element = item.find('span', class_='option-label')
                    label = label_element.get_text(strip=True).rstrip(':') if label_element else ""
                    text = item.get_text(strip=True)[3:] if item.get_text() else ""
                    options_data[label] = text
            
            # 从HTML元素中获取额外的选项（以防data-options中没有包含全部选项）
            option_items = options_container.find_all('div', class_='option-item')
            for item in option_items:
                label_element = item.find('span', class_='option-label')
                label = label_element.get_text(strip=True).rstrip(':') if label_element else ""
                text = item.get_text(strip=True)[3:] if item.get_text() else ""
                if label and label not in options_data:  # 只添加不在options_data中的选项
                    options_data[label] = text
        
        # 来源
        question_meta = question_card.find('div', class_='question-meta')
        source_element = question_meta.find('span') if question_meta else None
        source = source_element.get_text(strip=True) if source_element else ""
        
        # 正确答案
        correct_answer_div = question_card.find('div', class_='correct-answer')
        correct_answer_element = correct_answer_div.find('span') if correct_answer_div else None
        correct_answer = correct_answer_element.get_text(strip=True) if correct_answer_element else ""
        
        # 知识点
        knowledge_point_element = question_card.find('span', class_='current-knowledge-point')
        knowledge_point = knowledge_point_element.get_text(strip=True) if knowledge_point_element else ""
        
        # 构建题目信息字典
        question_info = {
            'type': question_type,
            'question': question_text,
            'options': options_data,
            'source': source,
            'correct_answer': correct_answer,
            'knowledge_point': knowledge_point
        }
        
        return question_info
    
    def parse_questions_from_page(self, html_content):
        """
        从页面HTML中解析所有题目
        :param html_content: 页面HTML内容
        :return: 题目列表
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        question_cards = soup.find_all('div', class_='question-card')
        
        questions = []
        for card in question_cards:
            question_html = str(card)
            question_info = self.parse_question_from_html(question_html)
            if question_info:
                questions.append(question_info)
        
        return questions


class QuestionCrawler:
    """题目爬虫，用于获取题目数据"""
    
    def __init__(self):
        self.config = Config()
        self.parser = QuestionParser()
        self.session = httpx.Client()
        
        # 设置cookies
        for key, value in self.config.cookies.items():
            self.session.cookies.set(key, value)
    
    def get_questions(self, page=1, size=15, question_types=None, course="软件工程"):
        """
        获取题目列表
        :param page: 页码
        :param size: 每页数量
        :param question_types: 题目类型列表
        :param course: 课程名称
        :return: 题目列表
        """
        if question_types is None:
            question_types = ['单选题', '判断题', '填空题', '多选题']
        
        # 构建请求URL
        url = self.config.base_url + self.config.student_questions_endpoint
        params = {
            'page': page,
            'size': size,
            'course': course
        }
        
        # 添加题目类型参数
        for q_type in question_types:
            params.setdefault('questionTypes', []).append(q_type)
        
        # 发送请求
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            # 解析题目
            questions = self.parser.parse_questions_from_page(response.text)
            return questions
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return []
    
    def crawl_and_save_questions(self, output_file="questions.json", max_pages=5):
        """
        爬取题目并保存到文件
        :param output_file: 输出文件名
        :param max_pages: 最大爬取页数
        """
        all_questions = []
        
        for page in range(1, max_pages + 1):
            print(f"正在爬取第 {page} 页...")
            questions = self.get_questions(page=page)
            if not questions:
                print(f"第 {page} 页没有获取到题目，停止爬取")
                break
            
            all_questions.extend(questions)
            print(f"第 {page} 页获取到 {len(questions)} 道题目")
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_questions, f, ensure_ascii=False, indent=2)
        
        print(f"总共爬取到 {len(all_questions)} 道题目，已保存到 {output_file}")


# 使用示例
if __name__ == "__main__":
    crawler = QuestionCrawler()
    
    # 解析单个题目HTML示例
    sample_html = """
    <div class="question-card" style="opacity: 1; transform: translateY(0px); transition: 0.5s;">
        <div class="question-header">
            <span class="question-type">单选题</span>
        </div>
        <div class="question-text">在软件结构化设计中，好的软件结构设计应该力求做到（ ）。</div>
        <div class="options-container">
            <h6>选项：</h6>
            <div class="optionsContainer" data-options="{&quot;A&quot;: &quot;顶层扇出较少，中间层扇出较高，底层模块低扇入&quot;, &quot;B&quot;: &quot;顶层扇出较高，中间层扇出较少，底层模块高扇入&quot;, &quot;C&quot;: &quot;顶层扇入较少，中间层扇出较高，底层模块高扇入&quot;, &quot;D&quot;: &quot;顶层扇入较少，中间层扇入较高，底层模块低扇入&quot;}">
                <div class="option-item">
                    <span class="option-label">A:</span> 顶层扇出较少，中间层扇出较高，底层模块低扇入
                </div>
                <div class="option-item">
                    <span class="option-label">B:</span> 顶层扇出较高，中间层扇出较少，底层模块高扇入
                </div>
                <div class="option-item">
                    <span class="option-label">C:</span> 顶层扇入较少，中间层扇出较高，底层模块高扇入
                </div>
                <div class="option-item">
                    <span class="option-label">D:</span> 顶层扇入较少，中间层扇入较高，底层模块低扇入
                </div>
            </div>
        </div>
        <div class="question-meta">
            <div>
                <span>
                    <i class="bi bi-book me-1"></i>
                    来源：<span>练习题</span>
                </span>
            </div>
        </div>
        <div class="answer-section" id="answer-1359">
            <div class="correct-answer">
                <strong>正确答案：</strong>
                <span>"B"</span>
            </div>
        </div>
        <div class="knowledge-points-section mt-3">
            <div class="knowledge-points-header">
                <i class="bi bi-tags me-1"></i>
                <strong>知识点：</strong>
                <span class="current-knowledge-point text-muted">结构化设计</span>
            </div>
        </div>
    </div>
    """
    a_html ="""
<div class="question-card" style="opacity: 1; transform: translateY(0px); transition: 0.5s;">
                <div class="question-header">
                    <span class="question-type">判断题</span>
                    <!-- 删除按钮（仅管理员和教师可见） -->
                    
                </div>

                <div class="question-text">在用例文档中，前置条件是系统无法检测的。</div>

                <!-- 题目图片暂时不支持显示 -->

                <!-- 选择题选项显示 -->
                

                <!-- 判断题选项显示 -->
                <div class="options-container">
                    <h6>选项：</h6>
                    <div class="option-item">
                        <span class="option-label">A:</span> 对
                    </div>
                    <div class="option-item">
                        <span class="option-label">B:</span> 错
                    </div>
                </div>

                <!-- 填空题显示 -->
                

                <div class="question-meta">
                    <div>
                        <span>
                            <i class="bi bi-book me-1"></i>
                            来源：<span>练习题</span>
                        </span>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <!-- 标记按钮（仅学生可见） -->
                        <button class="mark-button" onclick="toggleMark(this, 1007)">
                            <i class="bi bi-bookmark"></i>
                            <span>标记</span>
                        </button>
                        <!-- 根据show_answer字段显示答案按钮 -->
                        <div>
                            <button class="toggle-answer-btn" onclick="toggleAnswer(this, 1007)">
                                <i class="bi bi-eye me-1"></i>查看答案
                            </button>
                        </div>
                    </div>
                </div>

                <!-- 答案和解析区域（根据show_answer字段显示） -->
                <div class="answer-section" id="answer-1007">
                    <div class="answer-header" onclick="toggleAnswer(this.querySelector('.toggle-answer-btn'))">
                        <span class="answer-title">
                            <i class="bi bi-lightbulb me-1"></i>答案与解析
                        </span>
                        <button class="toggle-answer-btn">
                            <i class="bi bi-eye-slash me-1"></i>隐藏答案
                        </button>
                    </div>

                    <div class="correct-answer">
                        <strong>正确答案：</strong>
                        <span>"B"</span>
                    </div>

                    <div class="answer-analysis">
                        <strong>答案解析：</strong>
                        <div>前置条件必须是系统能检测到的，它作为用例的入口限制。</div>
                    </div>
                </div>

                <!-- 知识点选择区域 -->
                <div class="knowledge-points-section mt-3">
                    <div class="knowledge-points-header">
                        <i class="bi bi-tags me-1"></i>
                        <strong>知识点：</strong>
                        <span class="current-knowledge-point text-muted">UML</span>
                        
                    </div>

                    <!-- 知识点管理按钮（仅教师和管理员可见） -->
                    
                </div>
            </div>
"""
    parser = QuestionParser()
    question_info = parser.parse_question_from_html(a_html)
    print("解析的题目信息：")
    print(json.dumps(question_info, ensure_ascii=False, indent=2))