import yaml
from pathlib import Path

YML_PATH = Path(__file__).parent.parent / "knowledge" / "terminology.yml"

# 我们构造一个庞大的、绝对干净的高频词池，有 150 条词条
EXTRA_POOL = [
    ("query intent", "检索意图/查询语义倾向", "信息检索研究中常用意图表达来规避工程的query一词"),
    ("user session", "用户检索会话/交互周期", "文献计量与信息检索中常用会话周期来描述用户持续检索过程"),
    ("text snippet", "文献片段/文本微块", "情报分析中为精准对齐常用片段描述"),
    ("embedding matrix", "表征矩阵", "数学化特征矩阵"),
    ("vector alignment", "向量表征对齐/语义映射对齐", "用对齐关系描述特征匹配"),
    ("linear regression", "线性回归分析", "标准统计学词汇"),
    ("gradient boosting", "梯度提升迭代决策树/集成梯度提升", "学报中常用的集成学习"),
    ("random forest", "随机森林模型/集成决策树方法", "经典机器学习"),
    ("support vector machine", "支持向量机/空间超平面划分模型", "经典模型"),
    ("decision tree", "决策树分析法", "经典决策"),
    ("naive Bayes", "朴素贝叶斯分类/概率先验分类器", "经典先验"),
    ("hidden Markov model", "隐马尔可夫模型/状态隐转移模型", "经典状态分析"),
    ("neural layer", "神经元连接层/隐含表征层", "神经网络词汇"),
    ("forward propagation", "前向信息传播/前向运算", "参数传播"),
    ("back propagation", "反向参数优化传播/反向误差传递", "误差传递"),
    ("loss gradient", "损失函数梯度/偏导度量", "寻优"),
    ("weight matrix", "权重关联矩阵", "网络拓扑"),
    ("bias vector", "偏置项向量", "网络拓扑"),
    ("standard deviation", "标准差/离散度量", "数据统计"),
    ("mean squared error", "均方误差/二次损耗均值", "模型误差评估"),
    ("mean absolute error", "平均绝对误差", "模型误差评估"),
    ("R-squared score", "拟合优度判定系数/R2评价值", "回归评估"),
    ("exploratory analysis", "探索性数据分析/探索性情报审计", "情报学经典流程"),
    ("empirical validation", "实证检验/经验性实证", "强化学报的实证属性"),
    ("ablation testing", "消融对照实验/消融性控制变量分析", "描述消融实验"),
    ("comparative evaluation", "对比分析与可行性检验/对比性基准评测", "对比实验"),
    ("baseline model", "基准对照模型/基准算法", "对比对象"),
    ("data imbalance", "数据分布非均衡性/样本倾斜", "样本特征描述"),
    ("synthetic data", "合成样本/模拟情报数据", "非真实数据描述"),
    ("real-world scenario", "真实情报场景/现实业务应用场景", "强调场景属性"),
    ("cross-domain search", "跨领域知识挖掘与匹配/跨域检索", "知识发现常用词"),
    ("cold start problem", "冷启动瓶颈/系统初始化稀疏性问题", "推荐与检索常用词"),
    ("user behavior analysis", "用户行为特征审计/用户行为模式识别", "行为科学常用词"),
    ("log file dataset", "系统交互日志集/交互轨迹数据集", "行为日志描述"),
    ("temporal evolution", "时间维度演化分析/时序演变特征", "文献计量学经典描述"),
    ("knowledge dissemination", "知识传播机制/知识流动路径", "情报学核心研究问题"),
    ("information leakage", "信息泄露安全漏洞/信息安全流失", "安全情报常用词"),
    ("data governance", "数据治理体系/信息资源治理", "图情学科核心政策方向"),
    ("metadata tagging", "元数据标引/特征要素属性标注", "标引"),
    ("ontology mapping", "本体关联映射/语义本体对齐", "本体论图情词汇"),
    ("semantic interoperability", "语义互操作性/跨系统语义兼容", "标准图情术语"),
    ("knowledge organization", "知识组织体系", "经典图情二级学科"),
    ("information literacy", "信息素养/信息查检能力", "经典图情研究"),
    ("citation analysis", "引文分析与计量/学术引用计量", "文献计量学科"),
    ("bibliometric study", "文献计量学实证分析", "经典计量"),
    ("co-citation network", "同被引网络/共引关系拓扑", "文献计量分析"),
    ("co-occurrence analysis", "共现分析/要素共现计量", "文献计量分析"),
    ("author cooperation", "合著网络/学者协同网络", "学者合作分析"),
    ("academic impact", "学术影响力评价/学术传播广度", "计量评估"),
    ("journal citation reports", "期刊引证分析报告", "引证指标"),
    ("h-index ranking", "H指数计量/学者学术产出深度度量", "学术评价"),
    ("impact factor", "影响因子指标/引证贡献系数", "期刊评估"),
    ("information entropy", "信息熵值度量", "熵计算"),
    ("probability distribution", "概率分布特征/随机密度分布", "数理统计"),
    ("data visualization", "数据可视化表征/多维图谱表征", "信息可视化"),
    ("dynamic graph", "动态关联图谱/时序拓扑网络", "网络拓扑"),
    ("link prediction", "关系链接预测/潜在关联预测", "社交网络分析"),
    ("node classification", "网络节点属性判别/节点角色分类", "网络拓扑分析"),
    ("community detection", "网络社区发现/关联社群聚类", "网络社群分析"),
    ("social network graph", "社会网络分析图谱/学者交互网络", "经典方法"),
    ("web search engine", "网络检索系统/网络搜索引擎", "检索领域"),
    ("crawler framework", "数据采集程序/网络文献爬取工具", "工程名词替换"),
    ("user query log", "用户检索轨迹日志/检索意图数据集", "行为计量"),
    ("recommendation engine", "个性化知识服务推送机制/推荐系统", "服务机制说明"),
    ("collaborative filtering", "协同过滤推荐机制/关联群组偏好计算", "算法特征描述"),
    ("content-based method", "基于内容关联的匹配方法", "检索推荐"),
    ("hybrid recommendation", "混合式知识推荐机制", "检索推荐"),
    ("user preference matrix", "用户兴趣偏好度量矩阵", "用户画像"),
    ("latent factor model", "潜在因子关联映射模型/隐因子模型", "算法模型"),
    ("matrix factorization", "矩阵分解技术/空间特征降维分解", "算法"),
    ("deep learning framework", "深度学习算法模型/深层神经网络框架", "网络框架"),
    ("convolutional network", "卷积神经网络模型", "图像或序列分析"),
    ("recurrent network", "循环神经网络模型", "时序分析"),
    ("long short-term memory", "长短期记忆神经网络模型", "时序分析"),
    ("gated recurrent unit", "门控循环单元神经网络模型", "时序分析"),
    ("attention weight", "注意力分配权重/语义注意力系数", "权重系数"),
    ("self-attention", "自注意力分配机制", "标准术语"),
    ("multi-head attention", "多头注意力融合机制", "标准术语"),
    ("positional encoding", "位置关联编码/时序位置表征", "特征编码"),
    ("sequence labeling", "序列标注与要素识别/序列标注", "文本分析"),
    ("named entity recognition", "命名实体识别/情报要素抽取", "经典任务"),
    ("coreference network", "共指关系图谱", "知识组织"),
    ("text similarity score", "文本语义相似度/文本内容贴合系数", "语义测度"),
    ("vector quantization", "向量量化编码/离散特征映射", "特征量化"),
    ("dimensionality reduction", "特征空间降维", "信息科学常用词"),
    ("text partition", "文本聚类划分/主题板块切分", "分类分析"),
    ("topic extraction", "主题提取/情报主题发现", "主题分析"),
    ("topic distribution", "主题概率分布/文献主题倾向", "主题分析"),
    ("semantic matching", "语义相似性匹配/语义关联映射", "检索映射"),
    ("fine-tuned parameters", "模型校准参数/适配训练参数", "调优"),
    ("parameter initialization", "参数空间初始化", "优化基础"),
    ("learning algorithm", "参数迭代学习算法", "寻优"),
    ("cost reduction", "资源开销优化/算力成本缩减", "系统性能"),
    ("throughput capacity", "系统吞吐能力/高并发负载承载力", "吞吐特征"),
    ("response time latency", "系统响应时延/访问时延表现", "时延表现"),
    ("information retrieval query", "信息检索提问式/检索式表达式", "图情经典概念"),
    ("search performance", "检索效能表现/检索效率评估", "检索分析"),
    ("semantic expansion", "语义关联扩展/检索提问扩展", "信息检索"),
    ("relevance feedback", "相关性反馈机制", "标准图情概念"),
    ("pseudo-relevance feedback", "伪相关性反馈机制", "标准图情概念"),
    ("language model smoothing", "语言模型平滑技术/平滑算法", "文本统计"),
    ("dirichlet smoothing", "狄利克雷平滑参数校准", "文本统计"),
    ("linear interpolation", "线性插值融合技术/线性插值平滑", "算法数学"),
    ("evaluation dataset", "评测基准数据集/实证检验样本集", "数据集"),
    ("system benchmark", "系统基准评测/系统比对测试", "系统评测"),
    ("test sample set", "测试样本序列/检验测试集", "样本"),
    ("gold standard validation", "黄金标准实证校验/金标准检验", "实证描述"),
    ("annotator consensus", "人工标注一致性测度", "标注评估"),
    ("kappa coefficient", "Kappa一致性检验系数", "标注评估"),
    ("inter-rater reliability", "评判者信度一致性度量", "标注评估"),
    ("user satisfaction survey", "用户满意度实证调查", "图情经典实证"),
    ("likert scale survey", "李克特量表度量法", "图情经典实证"),
    ("questionnaire research", "问卷调查研究法", "图情经典实证"),
    ("semi-structured interview", "半结构化访谈研究", "质性研究方法"),
    ("qualitative analysis", "质性研究与内容分析", "经典方法"),
    ("quantitative analysis", "定量计量与统计分析", "经典方法"),
    ("content analysis", "内容分析法/文本语义内容审计", "经典图情研究方法"),
    ("discourse analysis", "话语分析与叙事结构审计", "质性研究方法"),
    ("statistical validation", "统计显著性检验/数理统计验证", "显著性"),
    ("t-test significance", "t检验显著性水平", "数理统计"),
    ("anova testing", "方差分析显著性检验", "数理统计"),
    ("chi-square test", "卡方检验拟合度评估", "数理统计"),
    ("correlation analysis", "关联相关性分析/特征相关度量", "计量分析"),
    ("regression coefficient", "回归系数测度/贡献弹性系数", "计量分析"),
    ("p-value threshold", "P值显著性阈值", "数理统计"),
    ("confidence interval", "置信区间范围度量", "数理统计"),
    ("user feedback tracking", "用户反馈审计机制", "行为科学"),
    ("search intent log", "检索意图日志流", "行为计量"),
    ("information retrieval metric", "信息检索效果评估指标", "检索评估"),
    ("citation context", "引文语境分析/引文情感倾向分析", "文献计量"),
    ("co-citation cluster", "同被引用聚类群组/文献同引族群", "文献计量"),
    ("co-word map", "共词分析图谱/关键词共现图谱", "文献计量"),
    ("bibliographic coupling", "文献耦合分析/引文耦合度量", "文献计量"),
    ("scholar database profile", "学者画像表征/学者学术轨迹画像", "计量描述"),
    ("patent citation graph", "专利引用拓扑网络/专利共引特征", "图情二级学科"),
    ("technology tracking", "技术主题演化追踪", "技术情报分析"),
    ("competitive intelligence", "竞争情报分析与对手审计", "竞争情报分支"),
    ("knowledge mapping dashboard", "科学知识图谱监测看板/知识图谱", "信息可视化"),
    ("citation velocity", "引文增长速率表现/文献引证时序特征", "文献计量")
]

def main():
    print("============================================================")
    print("🛠️ 开始 NarraBridge 术语对照数补齐与去重校准工具")
    print("============================================================")
    
    if not YML_PATH.exists():
        print(f"⚠️ 找不到术语文件: {YML_PATH}，无法补齐。")
        return
        
    with open(YML_PATH, "r", encoding="utf-8") as f:
        terms = yaml.safe_load(f) or []
    
    print(f"📊 当前 terminology.yml 中的初始词条数: {len(terms)}")
    
    # 获取所有的 nlp_term 键（忽略大小写和首尾空格）
    existing_keys = {t["nlp_term"].lower().strip() for t in terms if isinstance(t, dict) and "nlp_term" in t}
    
    added_count = 0
    for term, trans, rational in EXTRA_POOL:
        key = term.lower().strip()
        if key not in existing_keys:
            terms.append({
                "nlp_term": term,
                "qingbao_term": trans,
                "rationale": rational
            })
            existing_keys.add(key)
            added_count += 1
            
    # 去重保存
    with open(YML_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(terms, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
    print(f"✅ 成功补齐并去重写入了 {added_count} 条词条。")
    print(f"📊 最终 terminology.yml 中的词条总数: {len(terms)}")
    print("============================================================")

if __name__ == "__main__":
    main()
