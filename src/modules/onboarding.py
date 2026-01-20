# -*- coding: utf-8 -*-
"""
新手引导模块
负责首次运行时的环境检查、组件下载和实例部署引导
"""
import os
import time
import random
import tempfile
from pathlib import Path
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.layout import Layout
from rich.status import Status
from rich.control import Control
from rich.segment import Segment
from rich.style import Style

from ..core.p_config import p_config_manager
from ..ui.interface import ui
from .component_download.vscode_downloader import VSCODEDownloader
from .component_download.git_downloader import GitDownloader
from .deployment import deployment_manager

logger = structlog.get_logger(__name__)

class WipeRevealView:
    """擦除揭示视图，用于实现平滑的从色块到内容的过渡"""
    def __init__(self, renderable, reveal_width: int = 0, total_width: int = 80):
        self.renderable = renderable
        self.reveal_width = reveal_width
        self.total_width = total_width
        # 渐变色块字符 (从左到右: 细 -> 粗)
        self.block_chars = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
        self.block_style = Style(color="#0c0c0c")

    def __rich_console__(self, console, options):
        # 获取原始渲染结果
        lines = console.render_lines(self.renderable, options)
        
        for line in lines:
            current_width = 0
            # 这一行是否已经处理了渐变边缘
            edge_drawn = False
            
            new_line = []
            for segment in line:
                seg_len = segment.cell_length
                
                # Case 1: 完全在揭示区域内
                if current_width + seg_len <= self.reveal_width:
                    new_line.append(segment)
                    current_width += seg_len
                    
                # Case 2: 跨越揭示边界 (部分可见)
                elif current_width < self.reveal_width:
                    # 可见部分的长度
                    visible_len = self.reveal_width - current_width
                    
                    # 截取可见文本
                    text = segment.text
                    visible_text = ""
                    visible_cells = 0
                    for char in text:
                        char_width = 2 if ord(char) > 255 else 1
                        if visible_cells + char_width <= visible_len:
                            visible_text += char
                            visible_cells += char_width
                        else:
                            break
                    
                    if visible_text:
                        new_line.append(Segment(visible_text, segment.style))
                    
                    current_width += visible_len
                    
                    # 到了边界，绘制渐变边缘 (如果有空间)
                    if current_width < self.total_width:
                        # 计算剩余空间
                        remaining = self.total_width - current_width
                        if remaining > 0:
                            # 这里可以根据动画进度选择不同的块，但简化起见，我们使用一个反向的逻辑
                            # 或者仅仅在这里放一个过渡块。
                            # 为了平滑，我们在 reveal_width 的位置不放块，
                            # 而是让 reveal_width 逐渐增加。
                            # 这里的逻辑主要是"内容"结束了，后面接色块。
                            # 为了视觉上的连接，我们在内容和全色块之间放一个渐变块是不太容易的，
                            # 因为 reveal_width 是整数移动。
                            # 但我们可以根据 reveal_width 的小数部分(如果支持)来选块，这里只支持整数。
                            # 简单的做法：直接接实心块，或者留一个字符的过渡。
                            # 让我们简单点：直接接实心块，过渡效果靠 reveal_width 的快速变化。
                            pass
                    
                    # 标记当前位置已经是边界
                    edge_drawn = True
                    # 截断后续的 segment
                    break
                    
                # Case 3: 完全在遮罩区域 (不可见)
                else:
                    break
            
            # 如果渲染内容短于揭示宽度，需要填充空白（透明/背景）直到揭示边界
            if current_width < self.reveal_width:
                space_len = self.reveal_width - current_width
                new_line.append(Segment(" " * space_len))
                current_width += space_len

            # 填充剩余部分为色块
            if current_width < self.total_width:
                # 计算需要填充的长度
                fill_len = self.total_width - current_width
                
                # 第一个字符可以是渐变字符吗？
                # 如果我们想要"擦除"效果，应该是从全黑块逐渐变细直到消失，露出内容。
                # 也就是说，随着 reveal_width 增加，覆盖在上面的块变小。
                # reveal_width 处的块应该是 ▏ (最细)，然后右边是 █ (最粗/实心)。
                # 实际上：
                # Content | Edge | Solid Blocks
                # Edge block should be thin (▏) because it's about to disappear (reveal content).
                # Wait, if we are wiping FROM left TO right:
                # The "wiper" moves right.
                # Left of wiper is Content. Right of wiper is Blocks.
                # At the wiper position, the Block is shrinking.
                # So it goes █ -> ▉ -> ... -> ▏ -> (Content).
                # 但是我们的 loop 是基于 reveal_width (int) 的。
                # 为了实现"块变细"的效果，我们可以在 reveal_width + 1 的位置画一个根据 (step) 变化的块？
                # 我们的外部循环每次增加 step (比如 2)。
                # 这有点复杂。
                # 简化的方案：
                # 在 reveal_width 处画一个 ▌ (半块)，后面全画 █。
                # 这样至少有个过渡。
                
                # 添加一个过渡块
                new_line.append(Segment("▌", self.block_style))
                current_width += 1
                
                # 剩余填满实心块
                if current_width < self.total_width:
                    fill_len = self.total_width - current_width
                    # 构造实心块字符串
                    # 优化：不生成超长字符串，使用 Segment 的重复能力? Segment 不支持重复。
                    # 直接生成字符串即可。
                    new_line.append(Segment("█" * fill_len, self.block_style))

            yield from new_line
            yield Segment.line()

def _wipe_out_screen(duration: float = 0.5):
    """执行 Wipe Out 动画（全屏变黑）"""
    console = ui.console
    width, height = console.size
    
    # 渐变块定义
    BLOCK_CHARS = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
    
    # 步长，越小越平滑但越慢
    step = 1
    total_steps = (width // step) + len(BLOCK_CHARS) + 5
    sleep_time = duration / total_steps
    
    console.show_cursor(False)
    try:
        for current_col in range(0, width + len(BLOCK_CHARS) * step, step):
            draw_buffer = []
            
            for i, block_char in enumerate(BLOCK_CHARS):
                target_col = current_col - (i * step)
                if 0 <= target_col < width:
                    col_cmds = []
                    # #0c0c0c 对应的 ANSI 是 \x1b[38;2;12;12;12m
                    color_seq = "\x1b[38;2;12;12;12m"
                    
                    for r in range(height):
                        col_cmds.append(f"\x1b[{r+1};{target_col+1}H{color_seq}{block_char}")
                    
                    draw_buffer.append("".join(col_cmds))
            
            if draw_buffer:
                console.file.write("".join(draw_buffer))
                console.file.flush()
            
            time.sleep(sleep_time)
            
    finally:
        # 注意：这里不恢复光标，因为通常后面接 Wipe In
        pass

def wipe_transition(new_renderable=None, duration: float = 2.0):
    """
    转场动画：
    1. 黑色色块从左到右覆盖屏幕（Wipe Out）
    2. 新内容从左到右逐渐显示（Wipe In）
    """
    console = ui.console
    width, height = console.size
    
    # 计算时间
    half_duration = duration / 2
    
    # --- Step 1: Wipe Out (覆盖旧内容) ---
    _wipe_out_screen(duration=half_duration)
    
    try:
        # --- Step 2: Wipe In (显示新内容) ---
        if new_renderable:
            # 必须重置光标到左上角，否则Live会直接在色块下方追加打印
            console.control(Control.home())
            
            reveal_view = WipeRevealView(new_renderable, reveal_width=0, total_width=width)
            
            # 使用 Live 组件
            # 计算步长
            step_in = 1
            total_steps_in = (width // step_in) + 2
            sleep_time = half_duration / total_steps_in
            
            with Live(reveal_view, console=console, refresh_per_second=30, transient=False) as live:
                for w in range(0, width + step_in * 2, step_in):
                    reveal_view.reveal_width = min(w, width)
                    live.update(reveal_view)
                    time.sleep(sleep_time)
                
                # 最后确保完全显示
                reveal_view.reveal_width = width
                live.update(reveal_view)
                
    finally:
        console.show_cursor(True)
        # 恢复颜色
        console.file.write("\x1b[0m")
        console.file.flush()



def _type_text(text: str, style: str = "", end: str = "\n"):
    """打字机效果输出文本，带光标闪烁"""
    console = ui.console
    cursor_char = "▏"
    
    # 随机延迟范围
    min_char_delay = 0.01
    max_char_delay = 0.1  # 稍微调快一点，因为可能用于长文本
    min_line_delay = 0.2
    max_line_delay = 0.6
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        for char in line:
            # 打印字符
            console.print(char, end="", style=style)
            # 打印光标
            console.print(cursor_char, end="", style="bold white")
            console.file.flush()
            
            # 随机延迟
            time.sleep(random.uniform(min_char_delay, max_char_delay))
            
            # 回退光标 (使用退格键)
            console.file.write("\b")
            console.file.flush()
            
        # 行末清理光标
        console.print(" ", end="") # 用空格覆盖光标
        console.file.write("\b")   # 再退回来
        
        if i < len(lines) - 1:
            console.print() # 换行
            time.sleep(random.uniform(min_line_delay, max_line_delay))
            
    console.print(end=end) # 最后结束符

def run_onboarding():
    """运行新手引导流程"""
    # 初始清理
    ui.clear_screen()
    
    # 1. 欢迎界面
    welcome_title = Text("✨ 欢迎使用 MaiMai Start！", justify="center", style="bold cyan")
    
    # 预先定义好文本段落和样式
    welcome_segments = [
        ("检测到您是首次运行本程序。\n为了让您获得最佳体验，我们将引导您完成必要的环境配置和第一个实例的部署。\n\n", ""),
        ("引导内容：\n", "bold"),
        ("1. 检查并安装必要组件 (VSCode, Git)\n2. 部署您的第一个机器人实例", "")
    ]
    
    # ASCII Art
    ascii_lines = [
"""
 ooo        ooooo  .oooooo.           .oooooo..o     .                          . 
  &&.       .&&&` d&P`  `Y&b         d&P`    `Y&   .o&                        .o& 
  &&&b     d'&&& &&&                 Y&&bo.      .o&&&oo  .oooo.   ooo  q&b .o&&&oo 
  & Y&&. .P  &&& &&&         &&&&&&&  `*Y&&&&o.    &&&   `P  )&&   `&&&``&P   &&& 
  &  `&&&'   &&& &&&         *******      `“Y&&b   &&&    .oP&&&    &&&       &&& 
  &    Y     &&& `&&b    ooo         oo     .d&P   &&& . d&(  &&&   &&&       &&& . 
 o&o        o&&&o `Y&bood&P'         &*`&&&&&P'    `&&&` `Y&&&``qo d&&&b      `&&&` 
"""
    ]

    # 创建初始空面板用于转场
    # 获取屏幕宽度，使面板撑满屏幕
    screen_width = ui.console.size[0]
    panel_width = screen_width
    panel_height = 20 # 增加高度以容纳 ASCII Art
    
    # 构造居中的 ASCII Art Text 对象
    content_inner_width = panel_width - 6
    ascii_text = Text(style="#BADFFA")
    for line in ascii_lines:
        # 简单的居中计算
        padding = max(0, (content_inner_width - len(line)) // 2)
        ascii_text.append(" " * padding + line + "\n")
    ascii_text.append("\n") # ASCII 和文本之间的空行

    # 初始面板，包含 ASCII Art
    welcome_panel = Panel(
        ascii_text, 
        title=welcome_title,
        border_style="cyan",
        padding=(1, 2),
        expand=False,
        width=panel_width,
        height=panel_height
    )
    
    # 居中显示的 renderable
    centered_panel = Align.center(welcome_panel)
    
    # --- 组合动画：Wipe Out -> Wipe In (Reveal) -> Typewriter ---
    # 这一步将所有动画合并到一个流程中，避免多次渲染导致线框重叠
    
    # 1. Wipe Out (全屏变黑)
    _wipe_out_screen(duration=1.0)
    ui.console.control(Control.home())
    
    # 2. Wipe In & Typewriter combined in one Live context
    
    # 准备 Wipe In 视图
    width = ui.console.size[0]
    reveal_view = WipeRevealView(centered_panel, reveal_width=0, total_width=width)
    
    # transient=False 保持最终结果在屏幕上
    with Live(reveal_view, console=ui.console, refresh_per_second=30, transient=False) as live:
        # --- Phase A: Wipe In Animation (显示空线框) ---
        step_in = 1
        wipe_in_duration = 1.0 
        total_steps_in = (width // step_in) + 2
        sleep_time = wipe_in_duration / total_steps_in
        
        for w in range(0, width + step_in * 2, step_in):
            reveal_view.reveal_width = min(w, width)
            live.update(reveal_view)
            time.sleep(sleep_time)
            
        # 确保完全显示
        reveal_view.reveal_width = width
        live.update(reveal_view)
        
        # --- Phase B: Typewriter Animation (打字机填充内容) ---
        
        # 准备打字，初始包含 ASCII Art
        current_text = ascii_text.copy()
        # 更新 panel 的内容引用，这样 live.update() 时会显示新内容
        welcome_panel.renderable = current_text
        
        cursor_char = "▏"
        min_char_delay = 0.01
        max_char_delay = 0.08
        
        for text_part, style_part in welcome_segments:
            lines = text_part.split('\n')
            for i, line in enumerate(lines):
                for char in line:
                    current_text.append(char, style=style_part)
                    # 显示带光标的内容
                    display_text = current_text.copy()
                    display_text.append(cursor_char, style="bold white")
                    
                    welcome_panel.renderable = display_text
                    # 切换 Live 渲染对象为 centered_panel (直接显示，不再需要 WipeRevealView)
                    live.update(centered_panel)
                    
                    time.sleep(random.uniform(min_char_delay, max_char_delay))
                
                # 处理换行
                if i < len(lines) - 1:
                    current_text.append("\n")
                    # 换行时稍微停顿
                    time.sleep(random.uniform(0.1, 0.3))
        
        # 移除最后的光标
        welcome_panel.renderable = current_text
        live.update(centered_panel)
    
    # 恢复光标和颜色
    ui.console.show_cursor(True)
    ui.console.file.write("\x1b[0m")
    ui.console.file.flush()
    
    ui.console.print("\n")
    _type_text("是否开始配置向导？", end="")
    if not Confirm.ask("", default=True):
        _mark_as_not_first_run()
        return

    # 2. 组件检查与下载
    _check_and_install_components()
    
    # 3. 部署第一个实例
    _deploy_first_instance()
    
    _mark_as_not_first_run()
    
    end_panel = Panel(
        Align.center(
            "[bold green]🎉 新手引导完成！[/bold green]\n\n"
            "即将进入主菜单..."
        ),
        border_style="green",
        expand=False
    )
    
    wipe_transition(end_panel)
    ui.countdown(3)

def _check_and_install_components():
    """检查并安装组件"""
    # 准备新界面内容
    header_panel = Panel("[bold yellow]步骤 1/2: 环境检查与组件安装[/bold yellow]", border_style="yellow")
    
    # 执行转场动画进入新界面
    wipe_transition(header_panel)
    
    temp_dir = Path(tempfile.gettempdir()) / "maicore_downloads"
    os.makedirs(temp_dir, exist_ok=True)

    # --- VSCode ---
    with ui.console.status("[bold cyan]正在检查 Visual Studio Code...[/bold cyan]", spinner="dots") as status:
        time.sleep(0.8) # 稍微停顿展示动画
        vscode = VSCODEDownloader()
        installed, msg = vscode.check_installation()
        
        if installed:
            ui.console.print(f"✅ {msg}", style="green")
        else:
            status.stop() # 停止spinner以便交互
            ui.print_warning("❌ 未检测到 Visual Studio Code")
            _type_text("是否立即下载并安装 Visual Studio Code？(推荐)", end="")
            if Confirm.ask("", default=True):
                vscode.download_and_install(temp_dir)
            else:
                ui.print_info("已跳过 VSCode 安装")

    # --- Git ---
    with ui.console.status("[bold cyan]正在检查 Git...[/bold cyan]", spinner="dots") as status:
        time.sleep(0.8)
        git = GitDownloader()
        installed, msg = git.check_installation()
        
        if installed:
            ui.console.print(f"✅ {msg}", style="green")
        else:
            status.stop()
            ui.print_warning("❌ 未检测到 Git")
            if Confirm.ask("是否立即下载并安装 Git？(推荐)", default=True):
                git.download_and_install(temp_dir)
            else:
                ui.print_info("已跳过 Git 安装")
            
    ui.print_info("\n环境检查完成，按回车键继续...")
    ui.console.input()

def _deploy_first_instance():
    """部署第一个实例"""
    # 准备新界面内容
    header_panel = Panel("[bold yellow]步骤 2/2: 部署第一个实例[/bold yellow]", border_style="yellow")
    
    # 执行转场动画
    wipe_transition(header_panel)
    
    _type_text("MaiCore Start 支持一键部署 MaiBot 和 MoFox 等机器人实例。")
    
    ui.console.print()
    _type_text("是否现在部署您的第一个机器人实例？", end="")
    if Confirm.ask("", default=True):
        try:
            deployment_manager.deploy_instance()
        except Exception as e:
            ui.print_error(f"部署过程中发生错误: {str(e)}")
            logger.error("新手引导部署失败", error=str(e))
    else:
        ui.print_info("已跳过部署，您可以稍后在主菜单中进行部署。")

def _mark_as_not_first_run():
    """标记为非首次运行"""
    p_config_manager.set("first_run", False)
    p_config_manager.save()
    logger.info("已更新 first_run 标志为 False")
