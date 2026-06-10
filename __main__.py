import sys
import argparse
from narrabridge import translate_pipeline, entry_pipeline, review_pipeline

def main():
    """
    NarraBridge CLI 主入口点，解析子命令并运行相对应的 Pipeline。
    """
    parser = argparse.ArgumentParser(description="NarraBridge 命令行学术重构与对齐引擎")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # translate 子命令: 串联 5 个 Agent 自动执行翻译
    translate_parser = subparsers.add_parser("translate", help="代码项目到情报学论文的一键翻译流程")
    translate_parser.add_argument("project_path", type=str, help="待翻译的代码库绝对或相对路径")

    # entry 子命令: 根据技术关键词提供学术切入点引导
    entry_parser = subparsers.add_parser("entry", help="根据 NLP 技术栈发掘潜在的情报学研究方向")
    entry_parser.add_argument("query", type=str, help="以逗号分隔的 NLP 关键词技术短语，如 'RAG, multi-agent'")

    # review 子命令: 对已有学术论文草稿进行同行评审
    review_parser = subparsers.add_parser("review", help="针对已有 Markdown 论文草稿运行审稿人评估")
    review_parser.add_argument("draft_path", type=str, help="已生成的 Markdown 格式草稿文件的文件路径")

    args = parser.parse_args()

    # 路由到对应的 Pipeline
    if args.command == "translate":
        translate_pipeline(args.project_path)
    elif args.command == "entry":
        entry_pipeline(args.query)
    elif args.command == "review":
        review_pipeline(args.draft_path)

if __name__ == "__main__":
    main()
