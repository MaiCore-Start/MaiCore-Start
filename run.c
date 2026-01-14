#include <windows.h>
#include <shlwapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#pragma comment(lib, "Shlwapi.lib")

// 常量定义
#define REQUIREMENTS_FILE "requirements.txt"
#define MAIN_SCRIPT_FILE "main_refactored.py"
#define DEFAULT_PIP_INDEX "https://pypi.tuna.tsinghua.edu.cn/simple"
#define DEFAULT_FALLBACK_INDEX "https://pypi.org/simple"

const char* VENV_DIRS[] = { "venv", ".venv", "env", ".env" };
const int VENV_DIRS_COUNT = 4;

// 工具函数：路径拼接
void join_path(char* dest, const char* p1, const char* p2) {
    PathCombineA(dest, p1, p2);
}

// 模拟 Python input() 暂停
void wait_for_enter() {
    int c;
    while ((c = getchar()) != '\n' && c != EOF);
}

// 模拟 subprocess.run
// flags: creation flags (e.g., CREATE_NEW_CONSOLE)
int run_command(const char* cmd, int flags) {
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    // CreateProcess 需要可修改的字符串
    char cmd_mutable[2048];
    strncpy(cmd_mutable, cmd, sizeof(cmd_mutable) - 1);
    cmd_mutable[sizeof(cmd_mutable) - 1] = '\0';

    if (!CreateProcessA(NULL, cmd_mutable, NULL, NULL, FALSE, flags, NULL, NULL, &si, &pi)) {
        return -1; // 启动失败
    }

    // 阻塞等待
    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exit_code;
    GetExitCodeProcess(pi.hProcess, &exit_code);

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return (int)exit_code;
}

// 逻辑 1: 获取 create_venv.exe 路径
void get_venv_exe_path(char* out_path) {
    char base_dir[MAX_PATH];
    char cwd[MAX_PATH];
    char candidate[MAX_PATH];

    // 获取当前 EXE 所在目录 (相当于 sys.frozen = True 时的 base_dir)
    GetModuleFileNameA(NULL, base_dir, MAX_PATH);
    PathRemoveFileSpecA(base_dir);

    GetCurrentDirectoryA(MAX_PATH, cwd);

    // 1. 程序实际目录
    join_path(candidate, base_dir, "create_venv.exe");
    if (PathFileExistsA(candidate)) {
        strcpy(out_path, candidate);
        return;
    }

    // 2. 当前工作目录
    join_path(candidate, cwd, "create_venv.exe");
    if (PathFileExistsA(candidate)) {
        strcpy(out_path, candidate);
        return;
    }

    // 3. 项目根目录 (base_dir 的父目录)
    char parent_dir[MAX_PATH];
    strcpy(parent_dir, base_dir);
    PathRemoveFileSpecA(parent_dir); // 移一级
    join_path(candidate, parent_dir, "create_venv.exe");
    if (PathFileExistsA(candidate)) {
        strcpy(out_path, candidate);
        return;
    }

    // 4. 兜底
    join_path(candidate, base_dir, "create_venv.exe");
    strcpy(out_path, candidate);
}

// 逻辑: 查找现有的虚拟环境
int find_existing_venv(char* out_venv_path) {
    char cwd[MAX_PATH];
    GetCurrentDirectoryA(MAX_PATH, cwd);
    char check_path[MAX_PATH];
    char python_path[MAX_PATH];

    for (int i = 0; i < VENV_DIRS_COUNT; i++) {
        join_path(check_path, cwd, VENV_DIRS[i]);
        
        // 检查 venv_path / Scripts / python.exe
        join_path(python_path, check_path, "Scripts");
        join_path(python_path, python_path, "python.exe");

        if (PathFileExistsA(python_path)) {
            strcpy(out_venv_path, check_path);
            return 1; // Found
        }
    }
    return 0; // Not found
}

void get_venv_python(const char* venv_path, char* out_python) {
    join_path(out_python, venv_path, "Scripts");
    join_path(out_python, out_python, "python.exe");
}

void run_in_venv(const char* python_exe, const char* args) {
    char full_cmd[4096];
    // 注意: args 应该包含在引号中如果包含空格，这里简化处理
    snprintf(full_cmd, sizeof(full_cmd), "\"%s\" %s", python_exe, args);

    printf("[INFO] 执行命令: %s\n", full_cmd);
    
    int ret = run_command(full_cmd, 0);
    if (ret != 0) {
        printf("[ERROR] 命令执行失败: %s\n", full_cmd);
        exit(ret);
    }
}

// 在文件头部确保包含 windows.h
#include <windows.h>
#include <stdio.h>

// ... (之前的辅助函数保持不变) ...

int main() {
    // =======================================================
    // 设置控制台编码为 UTF-8，防止中文乱码
    // =======================================================
    SetConsoleOutputCP(65001); 
    // 可选：设置输入编码也为 UTF-8（如果需要读取中文输入）
    SetConsoleCP(65001);
    // =======================================================

    char venv_path[MAX_PATH];
    char venv_exe[MAX_PATH];
    char python_exe[MAX_PATH];
    
    // 1. 查找现有虚拟环境
    if (!find_existing_venv(venv_path)) {
        printf("[INFO] 未检测到可用虚拟环境，强制调用 create_venv.exe 创建虚拟环境...\n");
        
        get_venv_exe_path(venv_exe);
        
        if (!PathFileExistsA(venv_exe)) {
            printf("[ERROR] 未找到 create_venv.exe，尝试路径: %s\n", venv_exe);
            printf("按回车键退出...");
            wait_for_enter();
            return 1;
        }

        // 调用 create_venv.exe
        char cmd_venv[MAX_PATH + 2];
        snprintf(cmd_venv, sizeof(cmd_venv), "\"%s\"", venv_exe);

        // 注意：被调用的子进程通常会继承父进程的控制台。
        // 如果子进程也是输出 UTF-8 的，这里正好匹配。
        int result = run_command(cmd_venv, CREATE_NEW_CONSOLE);
        
        if (result == 0) {
            printf("[INFO] create_venv.exe创建虚拟环境成功。\n");
        } else {
            printf("[ERROR] create_venv.exe创建虚拟环境失败，返回码: %d\n", result);
            printf("按回车键退出...");
            wait_for_enter();
            return 1;
        }

        printf("请确认 create_venv.exe 已运行完成并成功创建虚拟环境后，按回车键继续...");
        wait_for_enter();

        if (!find_existing_venv(venv_path)) {
            printf("[ERROR] create_venv.exe创建虚拟环境后仍未检测到虚拟环境，程序退出。\n");
            printf("按回车键退出...");
            wait_for_enter();
            return 1;
        }
    }

    get_venv_python(venv_path, python_exe);

    // 2. 检查并安装依赖
    if (!PathFileExistsA(REQUIREMENTS_FILE)) {
        printf("[ERROR] 未找到 %s 文件！\n", REQUIREMENTS_FILE);
        return 1;
    }

    printf("[INFO] 正在检查并安装依赖...\n");

    char primary_index[256];
    if (GetEnvironmentVariableA("PIP_PRIMARY_INDEX", primary_index, sizeof(primary_index)) == 0) {
        strcpy(primary_index, DEFAULT_PIP_INDEX);
    }

    char fallback_index[256];
    if (GetEnvironmentVariableA("PIP_FALLBACK_INDEX", fallback_index, sizeof(fallback_index)) == 0) {
        strcpy(fallback_index, DEFAULT_FALLBACK_INDEX);
    }

    char pip_args[2048];
    snprintf(pip_args, sizeof(pip_args), 
        "-m pip install -r %s -i %s", 
        REQUIREMENTS_FILE, primary_index);
    
    if (strlen(fallback_index) > 0) {
        char extra[512];
        snprintf(extra, sizeof(extra), " --extra-index-url %s", fallback_index);
        strcat(pip_args, extra);
    }

    run_in_venv(python_exe, pip_args);

    // 3. 启动主程序
    if (!PathFileExistsA(MAIN_SCRIPT_FILE)) {
        printf("[ERROR] 未找到 %s 文件！\n", MAIN_SCRIPT_FILE);
        return 1;
    }

    printf("[INFO] 依赖安装完成，正在启动主程序...\n");
    
    run_in_venv(python_exe, MAIN_SCRIPT_FILE);

    return 0;
}