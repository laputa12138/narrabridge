import os
import sys
import shutil
import tempfile
import zipfile
import threading
import contextlib
from pathlib import Path
import gradio as gr

# 将父目录加入 path 并且设置 PYTHONPATH，保证在 gradio 进程和 Agent 内部能定位到未加包前缀的相对导入模块
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

GLOBAL_LOGS_LOCK = threading.Lock()
GLOBAL_LOGS = ""

class LogWriter:
    """用作上下文重定向的写入器，既输出到系统终端，又保存到全局 UI 日志缓冲区"""
    def write(self, text):
        global GLOBAL_LOGS
        with GLOBAL_LOGS_LOCK:
            GLOBAL_LOGS += text
            # 限制缓冲大小，防止内存占用过高
            if len(GLOBAL_LOGS) > 200000:
                GLOBAL_LOGS = GLOBAL_LOGS[-200000:]
        sys.__stdout__.write(text)
        
    def flush(self):
        sys.__stdout__.flush()

def get_console_logs():
    """供 UI 周期性调用获取全局日志"""
    global GLOBAL_LOGS
    with GLOBAL_LOGS_LOCK:
        return GLOBAL_LOGS

# 此时可以正常加载项目中的包
from __init__ import entry_pipeline, translate_pipeline, review_pipeline

# ----------------- Tab 1: 学术切入点发现 (Scene 1) -----------------
def run_entry_ui(query):
    global GLOBAL_LOGS
    if not query.strip():
        return "⚠️ 请输入技术栈或关键字！", None, "⚠️ 未输入有效内容"
    
    # 清空之前的日志，展示本次新请求
    with GLOBAL_LOGS_LOCK:
        GLOBAL_LOGS = f"=== 探索学术切入点: '{query}' ===\n"
        
    writer = LogWriter()
    # 仅在调用 pipeline 期间临时重定向 stdout 和 stderr，彻底防止与 uvicorn.Config 产生冲突
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        print(f"🚀 [UI] 启动学术方向发现引导...")
        try:
            res = entry_pipeline(query)
            
            # 组装格式化 MD 报告
            md = f"### 🎯 推荐的情报学研究方向: **{res.get('problem_type', '未知')}**\n"
            md += f"置信度评分: `{res.get('confidence', 0.0)}` \n\n"
            
            md += "#### 📚 推荐可供学习和引用的《情报学报》相似文献:\n"
            for idx, paper in enumerate(res.get("top_papers", [])):
                md += f"{idx+1}. **[{paper.get('id')}] {paper.get('title')}**\n"
                md += f"   - **推荐理由**: {paper.get('relevance_reason', '')}\n"
                md += f"   - **典型问题描述**: *\"{paper.get('excerpt', '')}\"*\n"
                
            # 组装词汇对照映射 DataFrame
            df_data = []
            for term in res.get("query_translations", []):
                df_data.append([
                    term.get("nlp_term", ""),
                    term.get("qingbao_term", ""),
                    term.get("query_used", "")
                ])
                
            print("✅ [UI] 学术切入点探索顺利结束。")
            return md, df_data, "✅ 探索完成！详细运行轨迹请参阅下方日志监视窗口。"
        except Exception as e:
            print(f"❌ [UI] 学术切入点探索出错: {e}")
            return f"❌ 运行失败: {e}", None, f"❌ 运行出错: {e}"


# ----------------- Tab 2: 一键代码到论文翻译 (Scene 2) -----------------
def run_translate_ui(project_path):
    global GLOBAL_LOGS
    if not project_path.strip():
        return "⚠️ 请输入本地代码库路径！", "", None, "⚠️ 未输入有效内容"
    
    path_obj = Path(project_path).expanduser().resolve()
    if not path_obj.exists():
        return f"❌ 找不到指定的本地路径: {project_path}", "", None, f"❌ 路径不存在: {project_path}"
    
    with GLOBAL_LOGS_LOCK:
        GLOBAL_LOGS = f"=== 启动代码到论文翻译管线: '{path_obj.name}' ===\n"
        
    writer = LogWriter()
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        print(f"🚀 [UI] 启动一键代码到论文翻译管线...")
        try:
            project_name = translate_pipeline(str(path_obj))
            
            # 读取生成出的论文草稿与评审报告
            output_dir = Path(__file__).parent.parent / "outputs" / project_name
            draft_file = output_dir / "paper_draft.md"
            review_file = output_dir / "review_report.md"
            
            draft_md = draft_file.read_text(encoding="utf-8") if draft_file.exists() else "⚠️ 未找到生成的论文草稿文件"
            review_md = review_file.read_text(encoding="utf-8") if review_file.exists() else "⚠️ 未找到生成的评审报告文件"
            
            # 打包产物
            zip_path = package_outputs(project_name)
            
            print("✅ [UI] 翻译管线运行顺利结束。")
            return draft_md, review_md, zip_path, "🎉 翻译管线全链路跑通！全部生成文件已就绪。"
        except Exception as e:
            print(f"❌ [UI] 翻译管线运行失败: {e}")
            return f"❌ 运行失败: {e}", f"❌ 运行失败: {e}", None, f"❌ 运行失败: {e}"

def package_outputs(project_name):
    """将 outputs/<project_name> 文件夹打包成 zip"""
    output_dir = Path(__file__).parent.parent / "outputs" / project_name
    if not output_dir.exists():
        return None
    
    zip_path = Path(tempfile.gettempdir()) / f"narrabridge_outputs_{project_name}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = Path(root) / file
                zipf.write(file_path, file_path.relative_to(output_dir.parent))
    return str(zip_path)


# ----------------- Tab 3: 论文规范评审 (Scene 3) -----------------
def run_review_ui(draft_path_input, uploaded_file):
    global GLOBAL_LOGS
    target_path = None
    if uploaded_file is not None:
        target_path = uploaded_file.name
    elif draft_path_input.strip():
        target_path = os.path.expanduser(draft_path_input.strip())
        
    if not target_path:
        return "⚠️ 请提供论文草稿！请输入路径或直接上传文件。", None, "⚠️ 未输入有效内容"
        
    path_obj = Path(target_path).resolve()
    if not path_obj.exists():
        return f"❌ 找不到指定的草稿路径: {target_path}", None, f"❌ 路径不存在: {target_path}"
        
    with GLOBAL_LOGS_LOCK:
        GLOBAL_LOGS = f"=== 启动同行评审: '{path_obj.name}' ===\n"
        
    writer = LogWriter()
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        print(f"🚀 [UI] 启动论文规范性同行审稿意见书生成...")
        try:
            report_path = review_pipeline(str(path_obj))
            
            report_md = Path(report_path).read_text(encoding="utf-8") if Path(report_path).exists() else "⚠️ 未找到生成的审稿意见书文件"
            
            print("✅ [UI] 审稿意见书生成顺利结束。")
            return report_md, str(report_path), "🎉 规范性审计报告已生成完毕！"
        except Exception as e:
            print(f"❌ [UI] 论文评审运行出错: {e}")
            return f"❌ 运行失败: {e}", None, f"❌ 运行失败: {e}"


CUSTOM_CSS = """
.container {
    max-width: 1200px;
    margin: 0 auto;
    font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
}
.header-panel {
    text-align: center;
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
    color: white;
    padding: 30px;
    border-radius: 12px;
    margin-bottom: 24px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
}
.header-panel h1 {
    font-size: 2.8rem;
    margin-bottom: 8px;
    font-weight: 900;
    letter-spacing: -0.05em;
}
.header-panel p {
    font-size: 1.2rem;
    opacity: 0.9;
    font-weight: 300;
}
.footer-logs {
    margin-top: 24px;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
"""

# ----------------- Gradio UI 页面布局 -----------------
def create_ui():
    with gr.Blocks(title="NarraBridge - 学术叙事转换平台") as demo:
        with gr.Column(elem_classes="container"):
            # 顶部 Premium Title Panel
            with gr.Column(elem_classes="header-panel"):
                gr.Markdown(
                    """
                    # 🚀 NarraBridge (叙事之桥)
                    ### 从工程技术代码到《情报学报》学术规范的智能对齐与翻译服务
                    """
                )
            
            # 主功能 Tabs
            with gr.Tabs(elem_classes="tab-container"):
                
                # Tab 1: 切入点发现
                with gr.Tab("💡 学术切入点发现"):
                    gr.Markdown("输入您的核心 NLP 技术栈或具体工程模块，系统将智能推荐在《情报学报》中最佳的情报学研究问题定义以及相似论文。")
                    with gr.Row():
                        entry_input = gr.Textbox(
                            label="输入技术栈 / 关键字 (如 multi-agent pipeline, RAG)", 
                            placeholder="请输入英文工程术语或核心模块名，以逗号分隔",
                            scale=4
                        )
                        entry_btn = gr.Button("探索学术切入点 🎯", variant="primary", scale=1)
                    
                    entry_status = gr.Markdown(value="等待输入...")
                    
                    with gr.Row():
                        with gr.Column(scale=3):
                            entry_output_md = gr.Markdown(label="推荐学术方向与参考论文")
                        with gr.Column(scale=2):
                            entry_output_df = gr.DataFrame(
                                headers=["原始工程术语 (NLP)", "建议学术术语 (情报学)", "底层检索词参考"],
                                label="推荐学术检索对照映射表",
                                wrap=True
                            )
                            
                    entry_btn.click(
                        fn=run_entry_ui,
                        inputs=[entry_input],
                        outputs=[entry_output_md, entry_output_df, entry_status]
                    )

                # Tab 2: 代码到论文翻译
                with gr.Tab("📝 代码到论文翻译"):
                    gr.Markdown("提供您本地的代码库路径，系统将依次运行：1. 技术画像提取；2. 学术问题映射；3. 叙事模式提取；4. 论文草稿撰写；5. 同行规范评审。")
                    with gr.Row():
                        translate_input = gr.Textbox(
                            label="本地代码库路径 (如 /home/yuanming/trust-eval)",
                            value="/home/yuanming/trust-eval",
                            placeholder="请输入绝对路径",
                            scale=4
                        )
                        translate_btn = gr.Button("一键启动翻译管线 🚀", variant="primary", scale=1)
                        
                    translate_status = gr.Markdown(value="等待启动...")
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("### 📄 《情报学报》风格论文草稿 (Draft)")
                            translate_draft = gr.Markdown(label="生成的论文草稿")
                        with gr.Column(scale=1):
                            gr.Markdown("### 📋 规范性同行评审意见 (Review Report)")
                            translate_review = gr.Markdown(label="生成的评审报告")
                            
                    with gr.Row():
                        download_zip = gr.File(label="📥 下载全套生成产物打包 (ZIP)")
                        
                    translate_btn.click(
                        fn=run_translate_ui,
                        inputs=[translate_input],
                        outputs=[translate_draft, translate_review, download_zip, translate_status]
                    )

                # Tab 3: 论文规范评审
                with gr.Tab("🔬 论文规范同行评审"):
                    gr.Markdown("直接上传已有的论文草稿 Markdown 文件，或者指定其本地路径，针对《情报学报》特有的学术规范和术语使用习惯，进行严苛的审稿审计。")
                    with gr.Row():
                        review_path_input = gr.Textbox(
                            label="论文草稿本地绝对路径 (选填)", 
                            placeholder="例如：/home/yuanming/trust-eval/outputs/paper_draft.md",
                            scale=3
                        )
                        review_upload = gr.File(
                            label="直接拖拽上传论文 Markdown 草稿 (.md)",
                            file_types=[".md"],
                            scale=2
                        )
                    
                    review_btn = gr.Button("一键启动同行评审 🔬", variant="primary")
                    review_status = gr.Markdown(value="等待启动...")
                    
                    with gr.Row():
                        review_output_md = gr.Markdown(label="《情报学报》规范性审稿意见书")
                        
                    download_report = gr.File(label="📥 下载同行评审报告书 (.md)")
                    
                    review_btn.click(
                        fn=run_review_ui,
                        inputs=[review_path_input, review_upload],
                        outputs=[review_output_md, download_report, review_status]
                    )

            # 底部实时日志监控 (Streaming Console Logs)
            with gr.Group(elem_classes="footer-logs"):
                gr.Markdown("#### 🖥️ 运行日志监控 (实时更新)")
                # 配合 every=1.0 周期刷新控制台 stdout
                log_viewer = gr.Code(
                    value="", 
                    language="python", 
                    label="控制台输出流", 
                    interactive=False
                )
                timer = gr.Timer(1.0)
                timer.tick(fn=get_console_logs, outputs=log_viewer)
                
    return demo

if __name__ == "__main__":
    # 创建 ui/ 文件夹
    Path(__file__).parent.mkdir(parents=True, exist_ok=True)
    demo = create_ui()
    # 重新在 launch 时注入 theme 和 css
    theme = gr.themes.Default(
        primary_hue="indigo",
        secondary_hue="slate",
        font=[gr.themes.GoogleFont("Outfit"), "sans-serif"]
    )
    # 启动本地 7860 端口
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, theme=theme, css=CUSTOM_CSS)
