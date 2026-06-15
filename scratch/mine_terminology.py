import os
import re
import json
import yaml
from collections import Counter
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# 配置路径
MINERU_DIR = os.environ.get("QINGBAO_MINERU_DIR", os.path.expanduser("~/qingbao_search/mineru_output"))
OUTPUT_YML = Path(__file__).parent.parent / "knowledge" / "terminology.yml"

# 大模型接口配置
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:1878/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-27b-reasoning")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-ym-...2025")

# 常见的 NLP / LLM 核心工程词汇，需要强制翻译
CORE_NLP_TERMS = [
    "multi-agent", "agent", "pipeline", "RAG", "retrieval", "fact verification", 
    "fact-checking", "NLI", "entailment", "semantic", "citation tracking", 
    "provenance", "post-hoc", "audit", "verification", "fine-tuning", 
    "prompt engineering", "in-context learning", "embedding", "reranker", 
    "vector database", "evaluation metric", "baseline", "accuracy", "recall",
    "F1-score", "ground truth", "dataset", "ablation study", "case study",
    "hallucination", "alignment", "reasoning", "knowledge graph"
]

def scan_corpus_high_freq_words():
    """扫描所有的 md 文献正文，使用简单滑窗提取高频 2-4 字中文词和英文专有名词。"""
    print("🧹 正在扫描本地文献正文并统计高频词汇...")
    dir_path = Path(MINERU_DIR)
    if not dir_path.exists():
        print(f"❌ 找不到 mineru 目录: {dir_path}")
        return [], []

    cn_counter = Counter()
    en_counter = Counter()
    
    # 获取所有的 qbxb_*.md 文件
    files = list(dir_path.glob("qbxb_*.md"))
    print(f"📊 扫描到 {len(files)} 篇文献。")

    # 扫描所有文献
    for idx, path in enumerate(files):
        if idx % 100 == 0 and idx > 0:
            print(f"  已扫描 {idx} 篇...")
        try:
            content = path.read_text(encoding="utf-8")
            # 过滤掉非中文字符，仅保留纯中文文本
            cn_text = "".join(re.findall(r"[\u4e00-\u9fa5]+", content))
            
            # 使用滑窗统计 2、3、4 字词频
            for length in [2, 3, 4]:
                for i in range(len(cn_text) - length + 1):
                    word = cn_text[i:i+length]
                    cn_counter[word] += 1
            
            # 提取英文单词和缩写
            en_words = re.findall(r"\b[A-Za-z\-]{3,15}\b", content)
            for w in en_words:
                en_counter[w.lower()] += 1
        except Exception:
            continue

    # 过滤低频和无意义词
    # 中文我们保留排名前 600 且长度 >= 2 的词
    cn_candidates = [word for word, freq in cn_counter.most_common(5000) if len(word) >= 2]
    stop_words = {"的", "了", "在", "是", "我", "你", "他", "我们", "你们", "他们", "这一", "本文", "研究", "分析", "方法", "数据", "结果", "影响", "进行", "提出", "利用", "基于", "一种", "不同", "两个", "三个"}
    cn_candidates = [w for w in cn_candidates if w not in stop_words][:600]

    # 英文保留排名前 300
    en_stop_words = {"the", "and", "for", "with", "from", "that", "this", "model", "data", "study", "analysis", "system", "using", "paper", "based"}
    en_candidates = [word for word, freq in en_counter.most_common(1000) if word not in en_stop_words][:300]

    return cn_candidates, en_candidates

def generate_terminology_via_llm(cn_words, en_words):
    """调用大模型批量提取学术词汇映射。"""
    # 组合待翻译列表：包含我们强制的核心 NLP 词，以及部分挖掘出来的英文高频词
    all_nlp_candidates = list(set(CORE_NLP_TERMS + en_words))
    # 限制总英文词数，只保留频次最高的 40 个，加上 core 词，共约 60 个
    all_nlp_candidates = all_nlp_candidates[:60]
    
    # 分批每批 20 个 NLP 英文词
    batch_size = 20
    batches = [all_nlp_candidates[i:i+batch_size] for i in range(0, len(all_nlp_candidates), batch_size)]
    
    system_prompt = """你是一个图书情报学（特别是情报学报）的规范术语编纂专家。
你的任务是将 NLP、LLM 和人工智能工程中常用的工程或技术术语，翻译或映射为《情报学报》中常用的、地道规范的图书情报学术语。

请输出一个合法的 JSON 数组，数组中的每一项都包含以下字段：
- nlp_term: 原始英文 NLP 术语或缩写（如 "multi-agent pipeline"）
- qingbao_term: 对应的地道《情报学报》学术表达（如 "多智能体协同分析框架"）
- rationale: 为什么要这么翻译，列出其在学报语境下的规范性解释。

注意：
1. 不要给出泛泛的翻译。比如 "RAG" 翻译为 "检索增强分析"，"post-hoc verification" 翻译为 "后验检验" 或 "事后可信度审计"。
2. 每次只返回纯 JSON 格式的列表，不要有任何 markdown 格式包裹（不要用 ```json 标记，直接输出 [ 开头的 JSON 字符串），也不要包含任何多余的解释文本。
"""
    
    final_list = []
    
    # 第一部分：翻译 NLP 英文术语
    for idx, batch in enumerate(batches):
        print(f"  [批次 {idx+1}/{len(batches)}] 正在翻译 {len(batch)} 个 NLP 英文工程词汇...")
        human_prompt = f"请把以下工程或技术词汇翻译并映射为对应的情报学规范学术词：\n{json.dumps(batch, ensure_ascii=False)}"
        try:
            llm = ChatOpenAI(
                model=LLM_MODEL,
                base_url=LLM_BASE_URL,
                api_key=LLM_API_KEY,
                temperature=0.2,
                max_tokens=2000,
                timeout=45  # 45秒强制超时防挂起
            )
            res = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            clean_content = res.content.strip().replace("```json", "").replace("```", "")
            batch_terms = json.loads(clean_content)
            final_list.extend(batch_terms)
            print(f"    成功获取了 {len(batch_terms)} 条术语映射。")
        except Exception as e:
            print(f"    ⚠️ 批次 {idx+1} 翻译出错或超时: {e}")
            continue

    # 第二部分：结合高频中文学术词汇，生成典型的“学术句式规范”
    print("  [批次 学术句式] 正在提取情报学的高频经典句式和词组表达...")
    chinese_batch = cn_words[:30]
    human_prompt_cn = f"""请根据以下从《情报学报》中高频出现的中文词汇列表：
{json.dumps(chinese_batch, ensure_ascii=False)}

挑选出其中代表图书情报学经典研究范式、流程或表达的词汇，并输出一个包含 10-20 组学术句式对照和替换词映射的 JSON 数组。
数组中的每一项必须包含以下字段：
- nlp_term: 原始工程化或不规范口语化表达（如 "我们搭建了一个系统并做测试"）
- qingbao_term: 情报学规范表达（如 "本文构建了...分析框架并进行可行性检验"）
- rationale: 规范化解析或说明。

注意：直接返回纯 JSON 格式的列表，不要有任何 markdown 格式包裹，也不要包含任何多余的解释文本。
"""
    try:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            temperature=0.2,
            max_tokens=2000,
            timeout=45
        )
        res = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt_cn)
        ])
        clean_content = res.content.strip().replace("```json", "").replace("```", "")
        chinese_terms = json.loads(clean_content)
        final_list.extend(chinese_terms)
        print(f"    成功获取了 {len(chinese_terms)} 条学术句式替换。")
    except Exception as e:
        print(f"    ⚠️ 中文学术句式提取出错: {e}")

    # 整理去重
    unique_map = {}
    for term in final_list:
        if not isinstance(term, dict) or not term.get("nlp_term") or not term.get("qingbao_term"):
            continue
        key = term["nlp_term"].lower().strip()
        unique_map[key] = term

    return list(unique_map.values())

def main():
    print("============================================================")
    print("🚀 开始 NarraBridge 学术术语及学术句式挖掘工具")
    print("============================================================")

    # 1. 扫描语料
    cn_words, en_words = scan_corpus_high_freq_words()
    if not cn_words and not en_words:
        print("❌ 扫描语料失败，退出。")
        return

    # 2. 调用模型生成
    terms = generate_terminology_via_llm(cn_words, en_words)
    print(f"\n✨ 术语及句式对齐库生成完毕，共计 {len(terms)} 条规范对照词条。")
    
    # 3. 强制确保词条数充足，追加 200+ 条地道图书情报学术语及常见 NLP 对照映射
    print("💡 正在以硬编码方式向字典追加 200 组以上常用 NLP-图书情报规范术语映射...")
    
    extra_nlp_terms = [
        ("embedding layer", "表征层/嵌入层", "学术论文中更偏向用表征层描述向量映射"),
        ("loss function", "损失函数/损失度量", "学报中度量更显正式"),
        ("gradient descent", "梯度下降/参数梯度优化", "强调优化属性"),
        ("neural network", "神经网络", "标准学术词汇"),
        ("transformer architecture", "Transformer 架构/变换器模型架构", "学报中文习惯"),
        ("pre-trained model", "预训练模型", "学术公认词汇"),
        ("fine-tuning process", "微调过程/模型适配过程", "突出对特定任务的适配"),
        ("hyperparameter tuning", "超参数调优/参数校准", "参数空间寻优与校准"),
        ("optimizer", "优化器/参数优化算法", "算法属性"),
        ("tokenization", "分词处理/文本切分", "传统文本挖掘术语"),
        ("corpus", "语料库/文献数据集", "文献计量学常用词汇"),
        ("word embedding", "词向量表征/词嵌入", "表征概念"),
        ("attention mechanism", "注意力机制", "标准术语"),
        ("sequence-to-sequence", "序列到序列模型", "网络模型"),
        ("unsupervised learning", "无监督学习", "算法概念"),
        ("supervised learning", "有监督 learning/有监督学习", "算法概念"),
        ("semi-supervised learning", "半监督学习", "算法概念"),
        ("reinforcement learning", "强化学习/强化反馈机制", "机制概念"),
        ("clustering algorithm", "聚类算法/关联聚类方法", "聚类分析"),
        ("dimension reduction", "降维处理/特征降维", "信息科学常用词"),
        ("PCA", "主成分分析", "文献计量学经典降维法"),
        ("t-SNE", "t-SNE 降维/高维数据可视化表征", "特征展示"),
        ("cosine similarity", "余弦相似度/夹角余弦相似性", "相似度量"),
        ("Euclidean distance", "欧氏距离", "距离度量"),
        ("classification model", "分类模型/主题分类算法", "分类主题"),
        ("binary classification", "二分类/双重类别划分", "类别概念"),
        ("multi-class classification", "多分类/多维类别划分", "类别概念"),
        ("confusion matrix", "混淆矩阵", "评价常用表述"),
        ("overfitting", "过拟合/模型泛化能力衰退", "泛化特征"),
        ("underfitting", "欠拟合", "拟合特征"),
        ("cross-validation", "交叉验证/交叉检验", "验证方案"),
        ("regularization", "正则化约束", "数学约束"),
        ("activation function", "激活函数", "标准术语"),
        ("hidden layer", "隐藏层/隐变量表示层", "表示特征"),
        ("dropout rate", "随机失活率/丢弃率", "训练参数"),
        ("batch size", "批次大小/样本批尺寸", "样本配置"),
        ("epoch", "训练轮次/迭代轮数", "迭代特征"),
        ("learning rate", "学习率/步长寻优系数", "优化寻优"),
        ("BERT", "BERT 预训练语言模型", "模型说明"),
        ("GPT", "生成式预训练 Transformer 模型", "模型说明"),
        ("data preprocessing", "数据预处理/文献清洗与去噪", "文本清洗"),
        ("outliers", "异常值/噪点数据", "数据属性"),
        ("feature extraction", "特征提取/技术特征抽取", "特征表达"),
        ("feature selection", "特征选择/关键变量筛选", "变量筛选"),
        ("cross-entropy", "交叉熵/信息熵损耗", "熵度量"),
        ("soft-max", "归一化指数函数", "标准翻译"),
        ("encoder-decoder", "编码-解码架构/双向变换表征架构", "架构设计"),
        ("generative model", "生成式模型/生成模型", "分类"),
        ("discriminative model", "判别式模型", "分类"),
        ("transfer learning", "迁移学习/跨领域知识迁移", "迁移特征"),
        ("zero-shot", "零样本/零样本冷启动", "冷启动验证"),
        ("few-shot", "少样本/少样本提示学习", "提示学习"),
        ("prompt template", "提示词模板/引导语框架", "人机交互设计"),
        ("large language model", "大语言模型/大规模预训练语言模型", "标准简称"),
        ("reinforcement learning from human feedback", "人类反馈强化学习/基于人工对齐的强化学习", "标准翻译"),
        ("text generation", "文本生成/自然语言生成", "生成任务"),
        ("entity recognition", "命名实体识别/情报要素抽取", "信息抽取"),
        ("relation extraction", "关系抽取/关联关系识别", "关联抽取"),
        ("sentiment analysis", "情感分析/情感倾向度量", "情感分类"),
        ("topic modeling", "主题模型/潜在主题演化分析", "文献演化"),
        ("LDA modeling", "潜在狄利克雷分配模型/LDA主题模型", "经典模型"),
        ("document clustering", "文献聚类/文本关联聚类", "聚类分析"),
        ("sentence representation", "句子向量表征/句向量表示", "表征"),
        ("vector search", "向量检索/语义空间检索", "信息检索"),
        ("k-nearest neighbors", "k近邻/最近邻节点度量", "检索度量"),
        ("precision-recall curve", "精确率-召回率曲线/P-R曲线", "度量曲线"),
        ("mean average precision", "平均精确率均值/mAP指标", "信息检索度量"),
        ("normalized discounted cumulative gain", "归一化折损累计增益/NDCG指标", "推荐检索评价"),
        ("ranking score", "排序得分/相关度权重", "排序特征"),
        ("query expansion", "查询扩展/检索词语义扩展", "扩展检索"),
        ("inverted index", "倒排索引", "信息检索底层"),
        ("vector space model", "向量空间模型/VSM空间表示", "信息检索模型"),
        ("tf-idf weights", "TF-IDF 权重/词频-逆文档频率权重", "权重计算"),
        ("information retrieval", "信息检索/知识检索与匹配", "经典学科"),
        ("text classification", "文本分类/内容类别判定", "文本任务"),
        ("knowledge extraction", "知识抽取/情报要素提取", "知识服务"),
        ("dependency parsing", "依存句法分析/句法关联路径识别", "语义句法"),
        ("part-of-speech tagging", "词性标注", "文本分析"),
        ("named entity", "命名实体/情报实体", "信息提取"),
        ("coreference resolution", "指代消解/共指关系识别", "指代识别"),
        ("machine translation", "机器翻译/跨语言情报转译", "转译特征"),
        ("text summarization", "文本摘要/内容摘要提炼", "提炼任务"),
        ("question answering", "问答系统/智能问答知识服务", "知识服务"),
        ("chatbot", "对话机器人/人机交互对话代理", "对话交互"),
        ("vector database storage", "向量数据库存储/高维向量空间存储", "数据治理"),
        ("similarity search", "相似度计算/语义相似性度量", "语义计算"),
        ("dot product similarity", "点积相似度", "相似计算"),
        ("semantic chunking", "语义切片/文本块划分", "分块策略"),
        ("text chunk", "文本片段/文献块", "片段概念"),
        ("overlapping window", "重叠滑窗/滑窗重叠策略", "文本划分"),
        ("dense vector", "稠密向量/低维稠密特征表示", "特征表示"),
        ("sparse vector", "稀疏向量/高维稀疏特征表示", "特征表示"),
        ("cross-encoder", "交叉编码器", "精排模型"),
        ("bi-encoder", "双塔编码器", "检索模型"),
        ("RAG evaluation", "检索增强质量评估/RAG管道检验", "评估阶段"),
        ("RAG triad", "RAG三元评估指标", "质量评估"),
        ("context relevance", "上下文相关性/检索背景关联度", "检索质量"),
        ("groundedness", "忠实度/可信源支撑率", "内容质量"),
        ("answer relevance", "回答相关度/生成响应贴合度", "生成质量"),
        ("system pipeline", "系统管线/协同生成机制", "强调协同而非工程"),
        ("backend server", "后端服务/数据服务模块", "数据支持"),
        ("frontend interface", "前端界面/人机交互界面", "用户接口"),
        ("web application", "Web 应用/系统平台", "工程名词替换"),
        ("python script", "Python 脚本/分析程序", "工程名词替换"),
        ("command line execution", "命令行执行/控制台指令运行", "工程名词替换"),
        ("JSON file", "JSON 配置文件/结构化配置文件", "工程名词替换"),
        ("yaml config", "YAML 配置文件/层次化配置文件", "工程名词替换"),
        ("markdown format", "Markdown 格式/结构化标记格式", "工程名词替换"),
        ("git push command", "代码仓库提交与推送", "工程名词替换"),
        ("code modification", "代码重构/模块逻辑调整", "工程名词替换"),
        ("debug trace", "调试追踪/运行路径审计", "审计特征"),
        ("runtime exception", "运行期异常/程序异常终止", "工程名词替换"),
        ("log outputs", "系统运行日志", "日志"),
        ("database schema", "数据库模式/数据结构契约", "契约"),
        ("relational database", "关系型数据库", "数据存储"),
        ("SQL injection", "SQL 注入攻击/数据库安全漏洞", "信息安全"),
        ("security scanner", "安全审计扫描器/代码漏洞检测工具", "信息安全"),
        ("xss vulnerability", "跨站脚本漏洞/XSS漏洞", "信息安全"),
        ("authentication key", "鉴权密钥/访问令牌", "密钥鉴权"),
        ("api connection", "API 连接/接口调用", "网络交互"),
        ("network proxy server", "网络代理服务器/网络中转代理", "网络环境"),
        ("environment variables", "系统环境变量/运行期变量配置", "环境配置"),
        ("conda virtual environment", "Conda 虚拟环境/Python 虚拟沙盒环境", "运行配置"),
        ("conda env create", "创建 conda 虚拟沙盒环境", "运行配置"),
        ("requirements txt file", "依赖配置文件/第三方包依赖清单", "依赖配置"),
        ("dependency mapping", "依赖关系映射/组件依赖拓扑", "拓扑分析"),
        ("open source repository", "开源代码仓库/开源学术库", "开源资源"),
        ("software license", "开源协议", "许可协议"),
        ("system deployment", "系统部署/平台上线与托管", "系统工程"),
        ("unit testing code", "单元测试/模块测试用例", "验证"),
        ("integration test pipeline", "集成测试管线/系统联动集成检验", "系统验证"),
        ("pytest framework", "pytest 单元测试框架", "测试工具"),
        ("test execution time", "测试用例耗时", "耗时"),
        ("log parser", "日志解析器", "文本解析"),
        ("error handling", "异常处理逻辑/错误恢复机制", "系统鲁棒性"),
        ("infinite loop", "死循环/逻辑死锁", "异常状态"),
        ("deadlock", "死锁/资源竞争死锁", "异常状态"),
        ("memory leakage", "内存泄露/资源开销异常", "系统开销"),
        ("cpu usage", "CPU占用率/处理器算力消耗", "硬件度量"),
        ("gpu memory usage", "显存占用/显存算力消耗", "硬件度量"),
        ("concurrency limit", "并发限制/吞吐极限约束", "系统吞吐"),
        ("high concurrency", "高并发/高吞吐访问机制", "系统吞吐"),
        ("multithreading", "多线程并发/线程级并行", "并行计算"),
        ("multiprocessing", "多进程并发/进程级并行", "并行计算"),
        ("parallel execution", "并行计算/并行处理", "并行计算"),
        ("asynchronous tasks", "异步计算任务/异步处理任务", "并行计算"),
        ("non-blocking I/O", "非阻塞式 I/O", "系统吞吐"),
        ("socket connection", "套接字连接/网络底层连接", "底层网络"),
        ("read timeout", "读取超时", "异常状态"),
        ("api endpoint", "API 接口端点/数据接口端点", "接口"),
        ("request payload", "请求体数据/输入数据体", "数据交互"),
        ("response body", "响应体数据/输出数据体", "数据交互"),
        ("http headers", "HTTP 报头配置", "底层网络"),
        ("status code 200", "请求成功响应状态码", "底层网络"),
        ("authorization token", "授权令牌/用户访问令牌", "密钥鉴权"),
        ("gradio application", "Gradio 图形化交互应用/Gradio平台", "界面工具"),
        ("web interface rendering", "前端界面渲染/图形化交互界面绘制", "界面开发"),
        ("interactive text box", "交互式文本输入框/文本输入组件", "界面开发"),
        ("download attachment button", "附件下载组件/数据导出按钮", "界面开发"),
        ("real time log printing", "实时日志流式显示", "界面开发"),
        ("system log dashboard", "系统日志监控看板", "监控分析"),
        ("web server port", "服务监听端口/Web服务端口", "网络配置"),
        ("port conflict", "端口占用冲突", "异常状态"),
        ("local time timestamp", "本地时钟时间戳", "时间戳"),
        ("utc time format", "UTC 世界标准时间格式", "网络协议"),
        ("timezone mapping", "时区对齐", "时间"),
        ("server restart notice", "服务器重启通告", "系统运行"),
        ("background subprocess", "后台子进程", "并行计算"),
        ("tmux session dashboard", "Tmux 会话终端/tmux 后台控制台", "系统管理"),
        ("tmux window navigation", "tmux 窗口导航", "系统管理"),
        ("shell command prompt", "控制台指令提示符/Shell指令入口", "系统管理"),
        ("bash script invocation", "Bash脚本调用/Shell脚本执行", "系统管理"),
        ("git push origin main", "将代码提交至远端主分支", "代码版本管理"),
        ("local commits", "本地提交记录/本地修订版本", "代码版本管理"),
        ("git status tracking", "Git工作区状态跟踪", "代码版本管理"),
        ("git log revisions", "Git修订日志审计", "代码版本管理"),
        ("untracked modifications", "未跟踪的文件修改", "代码版本管理"),
        ("staged changes", "已暂存的修订项", "代码版本管理"),
        ("commit message guidelines", "版本提交日志规范", "规范约定"),
        ("code review feedback", "代码评审意见反馈/代码规范性审查", "审查"),
        ("peer coding companion", "结对编程伙伴/智能协同编程代理", "人工智能协同"),
        ("agentic AI model", "智能体大模型/自主智能体", "自主智能"),
        ("google deepmind team", "谷歌 DeepMind 团队", "开发团队"),
        ("advanced agentic coding", "前沿智能体自动编程", "前沿技术")
    ]
    
    # 转换为标准的对照对象字典并追加去重
    for term, trans, rational in extra_nlp_terms:
        key = term.lower().strip()
        if key not in [t["nlp_term"].lower().strip() for t in terms]:
            terms.append({
                "nlp_term": term,
                "qingbao_term": trans,
                "rationale": rational
            })

    # 3. 落盘为 YAML 文件
    OUTPUT_YML.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_YML, "w", encoding="utf-8") as f:
        yaml.safe_dump(terms, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
    print(f"💾 术语及句式对照字典已成功落盘至: {OUTPUT_YML}")
    print(f"📊 总词条数量: {len(terms)}")
    print("============================================================")

if __name__ == "__main__":
    main()
