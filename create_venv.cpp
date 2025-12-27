#define _CRT_SECURE_NO_WARNINGS
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <algorithm>
#include <sstream>
#include <windows.h>
#include <shlobj.h>
#include <shellapi.h>

namespace fs = std::filesystem;

// 辅助：String 转 WString
std::wstring StringToWString(const std::string& str) {
    if (str.empty()) return std::wstring();
    int size_needed = MultiByteToWideChar(CP_UTF8, 0, &str[0], (int)str.size(), NULL, 0);
    std::wstring wstrTo(size_needed, 0);
    MultiByteToWideChar(CP_UTF8, 0, &str[0], (int)str.size(), &wstrTo[0], size_needed);
    return wstrTo;
}

// 辅助：WString 转 String
std::string WStringToString(const std::wstring& wstr) {
    if (wstr.empty()) return std::string();
    int size_needed = WideCharToMultiByte(CP_UTF8, 0, &wstr[0], (int)wstr.size(), NULL, 0, NULL, NULL);
    std::string strTo(size_needed, 0);
    WideCharToMultiByte(CP_UTF8, 0, &wstr[0], (int)wstr.size(), &strTo[0], size_needed, NULL, NULL);
    return strTo;
}

// 检查管理员权限
bool IsAdmin() {
    BOOL fIsRunAsAdmin = FALSE;
    PSID pAdminSID = NULL;
    SID_IDENTIFIER_AUTHORITY NtAuthority = SECURITY_NT_AUTHORITY;
    if (AllocateAndInitializeSid(&NtAuthority, 2, SECURITY_BUILTIN_DOMAIN_RID,
        DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &pAdminSID)) {
        CheckTokenMembership(NULL, pAdminSID, &fIsRunAsAdmin);
        FreeSid(pAdminSID);
    }
    return fIsRunAsAdmin;
}

// 提权重启
void RunAsAdmin(int argc, char* argv[]) {
    wchar_t szPath[MAX_PATH];
    if (GetModuleFileNameW(NULL, szPath, ARRAYSIZE(szPath))) {
        std::wstring params = L"--working-dir=\"" + fs::current_path().wstring() + L"\"";
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg.find("--working-dir") == std::string::npos) {
                params += L" " + StringToWString(arg);
            }
        }
        SHELLEXECUTEINFOW sei = { sizeof(sei) };
        sei.lpVerb = L"runas";
        sei.lpFile = szPath;
        sei.lpParameters = params.c_str();
        sei.nShow = SW_NORMAL;
        ShellExecuteExW(&sei);
        exit(0);
    }
}

// 核心功能：使用 CreateProcess 执行命令并获取/显示输出
// returnCode: 进程退出码
// output: 捕获的 stdout 输出内容
// printRealtime: 是否实时打印到控制台
int RunProcess(const std::string& cmd, std::string* output = nullptr, bool printRealtime = false) {
    HANDLE hRead, hWrite;
    SECURITY_ATTRIBUTES sa;
    sa.nLength = sizeof(SECURITY_ATTRIBUTES);
    sa.bInheritHandle = TRUE; // 允许子进程继承句柄
    sa.lpSecurityDescriptor = NULL;

    // 创建管道
    if (!CreatePipe(&hRead, &hWrite, &sa, 0)) return -1;

    // 确保读句柄不被继承（防止死锁）
    SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.hStdError = hWrite;  // stderr 重定向到管道
    si.hStdOutput = hWrite; // stdout 重定向到管道
    si.dwFlags |= STARTF_USESTDHANDLES;
    ZeroMemory(&pi, sizeof(pi));

    // CreateProcess 需要可写的 wchar_t 字符串
    std::wstring wCmd = StringToWString(cmd);
    std::vector<wchar_t> cmdBuf(wCmd.begin(), wCmd.end());
    cmdBuf.push_back(0);

    // 启动进程
    // CREATE_NO_WINDOW: 不弹黑框
    if (!CreateProcessW(NULL, cmdBuf.data(), NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return -1;
    }

    // 父进程关闭写端，否则 ReadFile 会一直阻塞
    CloseHandle(hWrite);

    // 读取输出
    DWORD bytesRead;
    CHAR buffer[4096];
    std::string fullOutput;

    while (true) {
        if (!ReadFile(hRead, buffer, sizeof(buffer) - 1, &bytesRead, NULL) || bytesRead == 0) {
            break;
        }
        buffer[bytesRead] = 0;
        std::string chunk(buffer);
        
        if (output) fullOutput += chunk;
        if (printRealtime) std::cout << chunk; // 实时打印
    }

    if (output) *output = fullOutput;

    // 等待进程结束
    WaitForSingleObject(pi.hProcess, INFINITE);
    
    DWORD exitCode = 0;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(hRead);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return exitCode;
}

// 查找系统 Python (恢复了 WindowsApps 的支持)
std::vector<std::string> FindSystemPython() {
    std::vector<std::string> paths;
    
    // 1. Where 命令
    std::string whereOutput;
    if (RunProcess("where python.exe", &whereOutput) == 0) {
        std::istringstream iss(whereOutput);
        std::string line;
        while (std::getline(iss, line)) {
            line.erase(std::remove(line.begin(), line.end(), '\n'), line.end());
            line.erase(std::remove(line.begin(), line.end(), '\r'), line.end());
            if (!line.empty() && fs::exists(line)) paths.push_back(line);
        }
    }

    // 2. 扫描 LocalAppData (WindowsApps 就在这里)
    char* buf = nullptr;
    size_t sz = 0;
    if (_dupenv_s(&buf, &sz, "LOCALAPPDATA") == 0 && buf) {
        std::string localAppData(buf);
        free(buf);

        // 显式检查 WindowsApps 目录
        fs::path winApps = fs::path(localAppData) / "Microsoft" / "WindowsApps";
        if (fs::exists(winApps)) {
            // WindowsApps 里的 python.exe 通常是 0KB 的重解析点，但 CreateProcess 能处理
            fs::path py = winApps / "python.exe";
            if (fs::exists(py)) paths.push_back(py.string());
        }

        // 检查 Programs/Python
        fs::path programs = fs::path(localAppData) / "Programs" / "Python";
        if (fs::exists(programs)) {
            for (const auto& entry : fs::directory_iterator(programs)) {
                fs::path py = entry.path() / "python.exe";
                if (fs::exists(py)) paths.push_back(py.string());
            }
        }
    }

    // 3. 扫描 Program Files
    const char* pfEnvs[] = { "ProgramFiles", "ProgramFiles(x86)" };
    for (const char* env : pfEnvs) {
        if (_dupenv_s(&buf, &sz, env) == 0 && buf) {
            fs::path base = fs::path(buf) / "Python";
            free(buf);
            if (fs::exists(base)) {
                for (const auto& entry : fs::directory_iterator(base)) {
                    fs::path py = entry.path() / "python.exe";
                    if (fs::exists(py)) paths.push_back(py.string());
                }
            }
        }
    }

    // 4. 扫描 C:\Python
    if (fs::exists("C:\\Python")) {
         // 简略逻辑，实际可能需要递归
    }

    // 去重
    std::sort(paths.begin(), paths.end());
    paths.erase(std::unique(paths.begin(), paths.end()), paths.end());
    
    // 将 WindowsApps 的路径放到最后，优先使用独立安装版
    // 因为 WindowsApps 可能会弹出商店窗口如果未安装完全
    std::stable_sort(paths.begin(), paths.end(), [](const std::string& a, const std::string& b) {
        bool aIsApp = a.find("WindowsApps") != std::string::npos;
        bool bIsApp = b.find("WindowsApps") != std::string::npos;
        if (aIsApp != bIsApp) return !aIsApp; // 非App在前
        return a > b; // 字典序降序 (版本号高在前)
    });

    return paths;
}

// 检查版本
bool CheckPythonVersion(const std::string& python_exe, std::string& out_version) {
    std::string cmd = "\"" + python_exe + "\" --version";
    std::string output;
    
    if (RunProcess(cmd, &output) != 0) return false;

    size_t pos = output.find("Python ");
    if (pos == std::string::npos) return false;

    std::string verStr = output.substr(pos + 7);
    verStr.erase(std::remove(verStr.begin(), verStr.end(), '\n'), verStr.end());
    verStr.erase(std::remove(verStr.begin(), verStr.end(), '\r'), verStr.end());
    out_version = verStr;

    int major = 0, minor = 0, patch = 0;
    sscanf(verStr.c_str(), "%d.%d.%d", &major, &minor, &patch);

    if (major > 3 || (major == 3 && minor >= 14)) {
        std::cout << "[WARNING] Python版本 " << verStr << " >= 3.14，不可用" << std::endl;
        return false;
    }
    if (major > 3 || (major == 3 && minor >= 8)) return true;
    return false;
}

int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);

    fs::path working_dir = fs::current_path();
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg.rfind("--working-dir=", 0) == 0) {
            std::string path_str = arg.substr(14);
            if (!path_str.empty() && path_str.front() == '"') path_str.erase(0, 1);
            if (!path_str.empty() && path_str.back() == '"') path_str.pop_back();
            working_dir = path_str;
            fs::current_path(working_dir);
            break;
        }
    }

    std::cout << "工作目录: " << working_dir.string() << std::endl;

    if (!IsAdmin()) {
        std::cout << "请求管理员权限..." << std::endl;
        RunAsAdmin(argc, argv);
        return 0;
    }

    std::cout << "正在查找 Python..." << std::endl;
    auto python_paths = FindSystemPython();

    if (python_paths.empty()) {
        std::cout << "未找到Python。" << std::endl;
        system("pause");
        return 1;
    }

    std::string suitable_python;
    for (const auto& exe : python_paths) {
        std::string ver;
        if (CheckPythonVersion(exe, ver)) {
            std::cout << "选定 Python: " << exe << " (" << ver << ")" << std::endl;
            suitable_python = exe;
            break;
        }
    }

    if (suitable_python.empty()) {
        std::cout << "没有符合版本 (3.8 - 3.13) 的 Python。" << std::endl;
        system("pause");
        return 1;
    }

    fs::path venv_dir = working_dir / "venv";
    if (fs::exists(venv_dir)) {
        std::cout << "清理旧环境..." << std::endl;
        try { fs::remove_all(venv_dir); Sleep(1000); } catch(...) {}
    }

    std::cout << "正在创建虚拟环境..." << std::endl;
    // 使用 CreateProcess 调用，确保支持 WindowsApps 路径
    std::string create_cmd = "\"" + suitable_python + "\" -m venv \"" + venv_dir.string() + "\"";
    
    if (RunProcess(create_cmd, nullptr, true) == 0) {
        std::cout << "\n虚拟环境创建成功!" << std::endl;
        
        fs::path req_path = working_dir / "requirements.txt";
        fs::path venv_py = venv_dir / "Scripts" / "python.exe";

        if (fs::exists(req_path) && fs::exists(venv_py)) {
            bool uv_ready = false;
            
            // 1. 检查 UV
            if (RunProcess("uv --version") == 0) {
                std::cout << "检测到 uv。" << std::endl;
                uv_ready = true;
            } else {
                std::cout << "正在安装 uv..." << std::endl;
                std::string install_uv = "\"" + suitable_python + "\" -m pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple";
                if (RunProcess(install_uv, nullptr, true) == 0) uv_ready = true;
                else std::cout << "uv 安装失败，将使用 pip。" << std::endl;
            }

            // 2. 安装依赖
            bool success = false;
            if (uv_ready) {
                std::cout << "正在使用 uv 安装依赖..." << std::endl;
                // 注意：uv pip install 需要指向 venv 的 python
                std::string uv_install = "uv pip install -r \"" + req_path.string() + 
                                         "\" -i https://pypi.tuna.tsinghua.edu.cn/simple --python \"" + 
                                         venv_py.string() + "\"";
                if (RunProcess(uv_install, nullptr, true) == 0) success = true;
            }

            if (!success) {
                std::cout << "正在使用 pip 安装依赖..." << std::endl;
                std::string pip_install = "\"" + venv_py.string() + "\" -m pip install -r \"" + 
                                          req_path.string() + "\" -i https://pypi.tuna.tsinghua.edu.cn/simple";
                if (RunProcess(pip_install, nullptr, true) == 0) success = true;
            }

            if (success) std::cout << "✅ 依赖安装完成。" << std::endl;
            else std::cout << "❌ 依赖安装失败。" << std::endl;
        }
    } else {
        std::cout << "创建虚拟环境失败。" << std::endl;
    }

    std::cout << "按回车退出..." << std::endl;
    std::cin.get();
    return 0;
}