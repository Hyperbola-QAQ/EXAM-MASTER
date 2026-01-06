class Config:
    # 基础URL配置
    base_url = "http://8.130.71.136:188"
    
    # 学生软件问题相关配置
    student_questions_endpoint = "/student/software-questions"
    
    # 默认请求参数
    default_params = {
        'page': 1,
        'size': 15,
        'questionTypes': ['判断题', '单选题', '多选题'],
        'course': '软件工程'
    }

    max_pages = 70
    
    # Cookie配置
    cookies = {
        'JSESSIONID': 'BFC3D78EA3BE54554636C7A811314B87',
        'remember-me-student': 'G1dGE5T6GxZwWz2hqbBR5kvehJJ1O7eFLzt_YvS3urQ'
    }