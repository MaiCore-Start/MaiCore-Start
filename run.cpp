#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <windows.h>
#include <cstdlib>
#include <algorithm>
#include <sstream>

namespace fs = std::filesystem;

// ==================== 常量定义 ====================
const std::string REQUIREMENTS = "requirements.txt";
const std::string MAIN_SCRIPT = "main_refactored.py";
const std::vector<std::string> VENV_DIRS = {"venv", ".venv", "env", ".env"};
const std::string PYTHON_INSTALLER = "./install/python-3.12.8-amd64.exe";
const std::string PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe";

// ==================== 工具函数 ====================

// 获取环境变量，如果不存在返回默认值
std::string get_env(const std::string& name, const std::string& default_value) {
    char* value = getenv(name.c_str());
    return value ? std::string(value) : default_value;
}

// 全局PIP索引配置
const std::string PRIMARY_PIP_INDEX = get_env("PIP_PRIMARY_INDEX", "https://pypi.tuna.tsinghua.edu.cn/simple");
const std::string FALLBACK_PIP_INDEX = get_env("PIP_FALLBACK_INDEX", "https://pypi.org/simple");

// 去除字符串首尾空格
std::string trim(const std::string& str) {
    size_t first = str.find_first_not_of(" \t\n\r");
    if (first == std::string::npos) return "";
    size_t last = str.find_last_not_of(" \t\n\r");
    return str.substr(first, last - first + 1);
}

// 字符串转小写
std::string to_lower(std::string str) {
    std::transform(str.begin(), str.end(), str.begin(), ::tolower);
    return str;
}

// 获取可执行文件所在目录
fs::path get_exe_dir() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    return fs::path(path).parent_path();
}

// 解析版本字符串为整数向量
std::vector<int> parse_version(const std::string& version) {
    std::vector<int> result;
    std::string num;
    for (char c : version) {
        if (c == '.') {
            if (!num.empty()) {
                try {
                    result.push_back(std::stoi(num));
                } catch (...) {
                    result.push_back(0);
                }
                num.clear();
            }
        } else if (isdigit(c)) {
            num += c;
        }
    }
    if (!num.empty()) {
        try {
            result.push_back(std::stoi(num));
        } catch (...) {
            result.push_back(0);
        }
    }
    return result;
}

// 版本比较：v1 >= v2
bool version_gte(const std::vector<int>& v1, const std::vector<int>& v2) {
    size_t maxLen = std::max(v1.size(), v2.size());
    for (size_t i = 0; i < maxLen; ++i) {
        int a = i < v1.size() ? v1[i] : 0;
        int b = i < v2.size() ? v2[i] : 0;
        if (a > b) return true;
        if (a < b) return false;
    }
    return true; // 相等
}

// 版本比较：v1 < v2
bool version_lt(const std::vector<int>& v1, const std::vector<int>& v2) {
    return !version_gte(v1, v2);
}

// ==================== 路径相关函数 ====================

// 获取 create_venv.exe 路径
fs::path get_venv_exe_path() {
    fs::path base_dir = get_exe_dir();
    
    // 1. 程序实际目录
    fs::path candidate = base_dir / "create_venv.exe";
    if (fs::exists(candidate)) {
        return candidate;
    }
    
    // 2. 当前工作目录
    candidate = fs::current_path() / "create_venv.exe";
    if (fs::exists(candidate)) {
        return candidate;
    }
    
    // 3. 项目根目录（父目录）
    candidate = base_dir.parent_path() / "create_venv.exe";
    if (fs::exists(candidate)) {
        return candidate;
    }
    
    // 4. 兜底：返回 base_dir / 'create_venv.exe'
    return base_dir / "create_venv.exe";
}

// 查找现有虚拟环境
fs::path find_existing_venv() {
    fs::path cwd = fs::current_path();
    for (const auto& name : VENV_DIRS) {
        fs::path venv_path = cwd / name;
        if (fs::exists(venv_path / "Scripts" / "python.exe")) {
            return venv_path;
        }
    }
    return fs::path(); // 返回空路径
}

// 获取虚拟环境中的 Python 可执行文件路径
fs::path get_venv_python(const fs::path& venv_path) {
    return venv_path / "Scripts" / "python.exe";
}

// ==================== 注册表相关函数 ====================

// 从注册表查找已安装的Python
std::pair<std::string, std::string> find_installed_python() {
    HKEY hives[] = {HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER};
    std::vector<int> min_version = {3, 8};
    std::vector<int> max_version = {3, 14};
    
    for (HKEY hive : hives) {
        HKEY pycore;
        if (RegOpenKeyExA(hive, "SOFTWARE\\Python\\PythonCore", 0, 
                          KEY_READ | KEY_WOW64_64KEY, &pycore) == ERROR_SUCCESS) {
            
            DWORD subKeyCount = 0;
            RegQueryInfoKeyA(pycore, NULL, NULL, NULL, &subKeyCount, 
                            NULL, NULL, NULL, NULL, NULL, NULL, NULL);
            
            for (DWORD i = 0; i < subKeyCount; ++i) {
                char version[256];
                DWORD versionLen = sizeof(version);
                
                if (RegEnumKeyExA(pycore, i, version, &versionLen, 
                                  NULL, NULL, NULL, NULL) == ERROR_SUCCESS) {
                    
                    std::vector<int> ver = parse_version(version);
                    
                    // 检查版本 >= 3.14，标记为不可用
                    if (version_gte(ver, max_version)) {
                        std::cout << "[WARNING] 检测到Python版本 " << version 
                                  << " >= 3.14，当前版本不可用" << std::endl;
                        continue;
                    }
                    
                    // 检查版本 >= 3.8 且 < 3.14
                    if (version_gte(ver, min_version) && version_lt(ver, max_version)) {
                        std::string installPathKey = std::string(version) + "\\InstallPath";
                        HKEY ipath;
                        
                        if (RegOpenKeyExA(pycore, installPathKey.c_str(), 0, 
                                         KEY_READ | KEY_WOW64_64KEY, &ipath) == ERROR_SUCCESS) {
                            
                            char pathBuf[MAX_PATH];
                            DWORD pathLen = sizeof(pathBuf);
                            DWORD type;
                            
                            if (RegQueryValueExA(ipath, "", NULL, &type, 
                                                (LPBYTE)pathBuf, &pathLen) == ERROR_SUCCESS) {
                                
                                fs::path exe = fs::path(pathBuf) / "python.exe";
                                if (fs::exists(exe)) {
                                    RegCloseKey(ipath);
                                    RegCloseKey(pycore);
                                    return {exe.string(), std::string(version)};
                                }
                            }
                            RegCloseKey(ipath);
                        }
                    }
                }
            }
            RegCloseKey(pycore);
        }
    }
    return {"", ""};
}

// ==================== 进程执行函数 ====================

// 在虚拟环境中运行命令
void run_in_venv(const fs::path& python_exe, const std::vector<std::string>& args) {
    // 构建命令行
    std::ostringstream cmd;
    cmd << "\"" << python_exe.string() << "\"";
    for (const auto& arg : args) {
        cmd << " " << arg;
    }
    
    std::string cmdStr = cmd.str();
    std::cout << "[INFO] 执行命令: " << cmdStr << std::endl;
    
    int result = system(cmdStr.c_str());
    
    if (result != 0) {
        std::cout << "[ERROR] 命令执行失败: " << cmdStr << std::endl;
        exit(result);
    }
}

// 使用 CreateProcess 运行外部程序（新控制台窗口）
bool run_process_new_console(const std::string& exePath, DWORD& exitCode) {
    STARTUPINFOA si = {};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi = {};
    
    std::string cmdLine = "\"" + exePath + "\"";
    std::vector<char> cmdLineBuf(cmdLine.begin(), cmdLine.end());
    cmdLineBuf.push_back('\0');
    
    if (CreateProcessA(
            NULL,                           // 应用程序名
            cmdLineBuf.data(),              // 命令行
            NULL,                           // 进程安全属性
            NULL,                           // 线程安全属性
            FALSE,                          // 不继承句柄
            CREATE_NEW_CONSOLE,             // 创建新控制台
            NULL,                           // 环境变量
            NULL,                           // 当前目录
            &si,                            // 启动信息
            &pi                             // 进程信息
        )) {
        
        // 等待进程完成
        WaitForSingleObject(pi.hProcess, INFINITE);
        GetExitCodeProcess(pi.hProcess, &exitCode);
        
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return true;
    }
    
    return false;
}

// ==================== 安装引导函数 ====================

// 提示用户安装 Python
void prompt_install_python() {
    std::cout << "[ERROR] 未检测到可用 Python 环境 (>=3.8 且 <3.14)。" << std::endl;
    std::cout << "是否安装 Python 3.12.8？(Y/N): ";
    
    std::string choice;
    std::getline(std::cin, choice);
    choice = to_lower(trim(choice));
    
    if (choice == "y") {
        if (fs::exists(PYTHON_INSTALLER)) {
            std::cout << "[INFO] 正在运行安装包: " << PYTHON_INSTALLER << std::endl;
            std::cout << "[INFO] 安装过程将阻塞等待完成，请耐心等待..." << std::endl;
            
            DWORD exitCode = 0;
            if (run_process_new_console(PYTHON_INSTALLER, exitCode)) {
                if (exitCode == 0) {
                    std::cout << "[INFO] Python安装完成" << std::endl;
                } else {
                    std::cout << "[ERROR] Python安装失败，返回码: " << exitCode << std::endl;
                }
            } else {
                std::cout << "[ERROR] 无法启动安装程序，错误码: " << GetLastError() << std::endl;
            }
        } else {
            std::cout << "[ERROR] 未找到 Python 安装包！您可以前往以下网址下载安装包：" << std::endl;
            std::cout << PYTHON_DOWNLOAD_URL << std::endl;
        }
        
        std::cout << "请安装完成后按回车键继续...";
        std::cin.get();
    } else {
        std::cout << "[INFO] 用户取消安装。程序退出。" << std::endl;
        exit(1);
    }
}

// ==================== 主函数 ====================

int main() {
    // 设置控制台编码为 UTF-8
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
    
    // 查找现有虚拟环境
    fs::path venv_path = find_existing_venv();
    
    if (venv_path.empty()) {
        std::cout << "[INFO] 未检测到可用虚拟环境，强制调用 create_venv.exe 创建虚拟环境..." 
                  << std::endl;
        
        fs::path venv_exe = get_venv_exe_path();
        
        if (!fs::exists(venv_exe)) {
            std::cout << "[ERROR] 未找到 create_venv.exe，尝试路径: " << venv_exe << std::endl;
            std::cout << "按回车键退出...";
            std::cin.get();
            return 1;
        }
        
        // 运行 create_venv.exe
        DWORD exitCode = 0;
        if (run_process_new_console(venv_exe.string(), exitCode)) {
            if (exitCode == 0) {
                std::cout << "[INFO] create_venv.exe创建虚拟环境成功。" << std::endl;
            } else {
                std::cout << "[ERROR] create_venv.exe创建虚拟环境失败，返回码: " 
                          << exitCode << std::endl;
                std::cout << "按回车键退出...";
                std::cin.get();
                return 1;
            }
        } else {
            std::cout << "[ERROR] 启动 create_venv.exe 失败，错误码: " 
                      << GetLastError() << std::endl;
            std::cout << "按回车键退出...";
            std::cin.get();
            return 1;
        }
        
        // 提示用户确认
        std::cout << "请确认 create_venv.exe 已运行完成并成功创建虚拟环境后，按回车键继续...";
        std::cin.get();
        
        // 再次检测虚拟环境
        venv_path = find_existing_venv();
        
        if (venv_path.empty()) {
            std::cout << "[ERROR] create_venv.exe创建虚拟环境后仍未检测到虚拟环境，程序退出。" 
                      << std::endl;
            std::cout << "按回车键退出...";
            std::cin.get();
            return 1;
        }
    }
    
    fs::path python_exe = get_venv_python(venv_path);
    
    // 检查 requirements.txt 是否存在
    if (!fs::exists(REQUIREMENTS)) {
        std::cout << "[ERROR] 未找到 " << REQUIREMENTS << " 文件！" << std::endl;
        return 1;
    }
    
    // 安装依赖
    std::cout << "[INFO] 正在检查并安装依赖..." << std::endl;
    
    std::vector<std::string> pip_cmd = {
        "-m", "pip", "install", "-r", REQUIREMENTS, "-i", PRIMARY_PIP_INDEX
    };
    
    if (!FALLBACK_PIP_INDEX.empty()) {
        pip_cmd.push_back("--extra-index-url");
        pip_cmd.push_back(FALLBACK_PIP_INDEX);
    }
    
    run_in_venv(python_exe, pip_cmd);
    
    // 检查主脚本是否存在
    if (!fs::exists(MAIN_SCRIPT)) {
        std::cout << "[ERROR] 未找到 " << MAIN_SCRIPT << " 文件！" << std::endl;
        return 1;
    }
    
    // 启动主程序
    std::cout << "[INFO] 依赖安装完成，正在启动主程序..." << std::endl;
    run_in_venv(python_exe, {MAIN_SCRIPT});
    
    return 0;
}