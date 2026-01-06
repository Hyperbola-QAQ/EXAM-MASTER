import httpx
import csv
from config import Config
from parser import QuestionParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

class QuestionCrawler:
    """题目爬虫，用于获取题目数据"""
    
    def __init__(self):
        self.config = Config()
        self.parser = QuestionParser()
        self.questions_lock = Lock()
        
        # 创建一个线程安全的会话池
        self.session_pool = ThreadPoolExecutor(max_workers=10)
        
    def create_session(self):
        """创建一个新的会话实例"""
        session = httpx.Client(timeout=30.0)
        for key, value in self.config.cookies.items():
            session.cookies.set(key, value)
        return session
    
    def get_questions(self, page_data):
        """
        获取题目列表
        :param page_data: 包含页码、大小、题目类型和课程信息的字典
        :return: 题目列表和页码
        """
        page = page_data['page']
        size = page_data['size']
        question_types = page_data['question_types']
        course = page_data['course']
        
        session = self.create_session()
        
        try:
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
            response = session.get(url, params=params)
            
            if response.status_code == 200:
                # 解析题目
                questions = self.parser.parse_questions_from_page(response.text)
                print(f"第 {page} 页获取到 {len(questions)} 道题目")
                return questions, page
            else:
                print(f"第 {page} 页请求失败，状态码: {response.status_code}")
                return [], page
        except Exception as e:
            print(f"第 {page} 页请求异常: {str(e)}")
            return [], page
        finally:
            session.close()
    
    def crawl_and_save_questions(self, output_file="questions.csv"):
        """
        多线程爬取题目并保存到CSV文件
        :param output_file: 输出文件名
        """

        # self.config.max_pages=1

        all_questions = []

        # 准备页码数据
        page_data_list = []
        for page in range(1, self.config.max_pages + 1):
            page_data = {
                'page': page,
                'size': 15,
                'question_types': ['单选题', '判断题', '多选题'],
                'course': "软件工程"
            }
            page_data_list.append(page_data)

        print(f"开始使用 {min(10, len(page_data_list))} 个线程并发爬取 {len(page_data_list)} 页...")
        
        # 使用线程池并发爬取
        with ThreadPoolExecutor(max_workers=min(10, len(page_data_list))) as executor:
            # 提交所有任务
            future_to_page = {executor.submit(self.get_questions, page_data): page_data['page'] 
                            for page_data in page_data_list}
            
            # 收集结果
            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    questions, page_num = future.result()
                    if questions:
                        all_questions.extend(questions)
                    else:
                        print(f"第 {page} 页没有获取到题目")
                except Exception as e:
                    print(f"处理第 {page} 页时发生异常: {str(e)}")

        print(f"总共爬取到 {len(all_questions)} 道题目")
        
        # 处理题目：转换判断题，分离空答案题目
        processed_questions, empty_answer_questions = self.process_questions(all_questions)
        
        # 保存正常题目到CSV文件
        self.save_questions_to_csv(processed_questions, output_file)
        
        # 保存空答案题目到单独的文件
        if empty_answer_questions:
            empty_output_file = output_file.replace('.csv', '_empty_answers.csv')
            self.save_questions_to_csv(empty_answer_questions, empty_output_file)
            print(f"空答案题目已保存到 {empty_output_file}")
        
        print(f"正常题目已保存到 {output_file}，共 {len(processed_questions)} 道题目")

    def process_questions(self, questions):
        """
        处理题目：转换判断题为A/B选项格式，分离空答案题目
        :param questions: 原始题目列表
        :return: 处理后的正常题目列表和空答案题目列表
        """
        processed_questions = []
        empty_answer_questions = []
        
        for q in questions:
            # 检查是否是判断题
            if q.get("type") == "判断题":
                q = self.convert_judgment_to_choice(q)

            if q.get("type") == "多选题":
                # "[""A"", ""B"", ""C"", ""D"", ""E""]"
                q["correct_answer"] = q["correct_answer"].replace("[", "").replace("]", "").replace(" ", "").replace("\"", "").replace("'", "").replace(",", "")
            
            # 检查答案是否为空
            if not q.get("correct_answer", "").strip():
                empty_answer_questions.append(q)
            else:
                processed_questions.append(q)
        
        return processed_questions, empty_answer_questions

    def convert_judgment_to_choice(self, question):
        """
        将判断题转换为A/B选项的单选题
        :param question: 判断题对象
        :return: 转换后的单选题对象
        """
        # 获取原答案
        original_answer = question.get("correct_answer", "").strip()
        
        # 设置A为正确，B为错误
        options = question.get("options", {})
        options["A"] = "正确"
        options["B"] = "错误"
        
        # 转换答案：如果是正确、是、对等，设为A；否则设为B
        if original_answer in ["正确", "是", "对", "1", "True", "Y", "T", "A"] or "A" in original_answer:
            question["correct_answer"] = "A"
        elif original_answer in ["错误", "否", "不对", "0", "False", "N", "F", "B"] or "B" in original_answer:
            question["correct_answer"] = "B"
        else:
            question["correct_answer"] = question["correct_answer"]
        
        question["options"] = options
        
        return question

    def save_questions_to_csv(self, questions, output_file):
        """
        将题目保存为CSV格式
        :param questions: 题目列表
        :param output_file: 输出文件名
        """
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ["题号", "题干", "A", "B", "C", "D", "E", "答案", "难度", "题型"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for i, q in enumerate(questions, 1):
                row = {
                    "题号": i,
                    "题干": q.get("question", ""),
                    "A": q.get("options", {}).get("A", ""),
                    "B": q.get("options", {}).get("B", ""),
                    "C": q.get("options", {}).get("C", ""),
                    "D": q.get("options", {}).get("D", ""),
                    "E": q.get("options", {}).get("E", ""),
                    "答案": q.get("correct_answer", "").strip('"'),
                    "难度": q.get("knowledge_point", ""),
                    "题型": q.get("type", "")
                }
                writer.writerow(row)

if __name__ == '__main__':
    crawler = QuestionCrawler()
    crawler.crawl_and_save_questions()