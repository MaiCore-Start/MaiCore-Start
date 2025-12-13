// 右下角多条消息提醒组件
function showMessage(msg, type = 'info', duration = 5000) {
    let container = document.getElementById('custom-message-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'custom-message-container';
        container.style.position = 'fixed';
        container.style.right = '32px';
        container.style.bottom = '32px';
        container.style.zIndex = 9999;
        container.style.display = 'flex';
        container.style.flexDirection = 'column-reverse';
        container.style.alignItems = 'flex-end';
        document.body.appendChild(container);
    }
    const box = document.createElement('div');
    box.className = 'custom-message-box';
    box.style.background = type === 'error' ? '#ffeaea' : (type === 'success' ? '#eaffea' : type === 'warn' ? '#fffbe6' : '#f5f5f5');
    box.style.color = type === 'error' ? '#d93026' : (type === 'success' ? '#1a7f37' : type === 'warn' ? '#b26a00' : '#333');
    box.style.minWidth = '180px';
    box.style.maxWidth = '320px';
    box.style.marginTop = '12px';
    box.style.padding = '14px 32px 18px 32px';
    box.style.borderRadius = '8px';
    box.style.fontSize = '16px';
    box.style.boxShadow = '0 2px 16px rgba(0,0,0,0.08)';
    box.style.textAlign = 'center';
    box.style.position = 'relative';
    box.style.opacity = 0;
    box.style.transform = 'translateX(60px)';
    box.style.transition = 'opacity 0.3s, transform 0.3s';
    box.innerText = msg;
    // 进度条
    const bar = document.createElement('div');
    bar.style.position = 'absolute';
    bar.style.left = 0;
    bar.style.bottom = 0;
    bar.style.height = '4px';
    bar.style.width = '0%';
    bar.style.borderRadius = '0 0 8px 8px';
    bar.style.background = type === 'error' ? '#ff4d4f' : (type === 'success' ? '#52c41a' : type === 'warn' ? '#faad14' : '#1890ff');
    bar.style.transition = `width linear ${duration}ms`;
    box.appendChild(bar);
    container.appendChild(box);
    // 动画滑入
    setTimeout(() => {
        box.style.opacity = 1;
        box.style.transform = 'translateX(0)';
        bar.style.width = '100%';
    }, 10);
    // 自动消失
    setTimeout(() => {
        box.style.opacity = 0;
        box.style.transform = 'translateX(60px)';
        setTimeout(() => {
            box.remove();
        }, 300);
    }, duration);
}
const apiBase = `${location.protocol}//${location.hostname}:${location.port}/api`;

const fieldLabels = {
    serial_number: "用户序列号",
    absolute_serial_number: "绝对序列号",
    version_path: "版本号",
    nickname_path: "实例昵称",
    bot_type: "Bot类型",
    mai_path: "麦麦本体路径",
    mofox_path: "墨狐本体路径",
    adapter_path: "适配器路径",
    napcat_path: "NapCat路径",
    napcat_version: "NapCat版本",
    venv_path: "虚拟环境路径",
    mongodb_path: "MongoDB路径",
    webui_path: "WebUI路径",
    qq_account: "QQ账号"
};

function createCard(name, data) {
    const card = document.createElement("div");
    card.className = "config-card";
    card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div class="config-title">${name}</div>
            <button class="btn btn-delete" title="删除" style="padding:2px 10px;font-size:14px;">×</button>
        </div>
        <div class="config-info">序列号: ${data.serial_number || ""}</div>
        <div class="config-info">Bot类型: ${data.bot_type || "MaiBot"}</div>
        <div class="config-info">版本: ${data.version_path || ""}</div>
        <div class="config-info">昵称: ${data.nickname_path || ""}</div>
        <div class="config-info">QQ账号: ${data.qq_account || ""}</div>
    `;
    card.onclick = (e) => {
        if (e.target.classList.contains("btn-delete")) return;
        showModal(name, data);
    };
    card.querySelector(".btn-delete").onclick = (e) => {
        e.stopPropagation();
        if (confirm(`确定要删除配置集 "${name}" 吗？`)) {
            fetch(`${apiBase}/configs/${name}`, { method: "DELETE" })
                .then(r => r.json()).then(res => {
                    if (res.success) loadConfigs();
                    else alert("删除失败: " + (res.msg || ""));
                });
        }
    };
    return card;
}

function renderConfigs(configs) {
    const list = document.getElementById("config-list");
    list.innerHTML = "";
    Object.entries(configs).forEach(([name, data]) => {
        list.appendChild(createCard(name, data));
    });
}

document.getElementById("add-config-btn").onclick = () => {
    // 获取全部配置集，生成唯一绝对序列号
    fetch(`${apiBase}/configs`).then(r => r.json()).then(configs => {
        const usedNums = new Set(Object.values(configs).map(c => parseInt(c.absolute_serial_number, 10) || 0));
        let absNum = Object.keys(configs).length + 1;
        while (usedNums.has(absNum)) absNum++;
        const emptyConfig = {
            serial_number: "",
            absolute_serial_number: absNum,
            version_path: "",
            nickname_path: "",
            bot_type: "MaiBot",  // 默认为MaiBot
            mai_path: "",
            mofox_path: "",  // 添加mofox_path字段
            adapter_path: "",
            napcat_path: "",
            napcat_version: "",
            venv_path: "",
            mongodb_path: "",
            webui_path: "",
            qq_account: "",
            install_options: {
                install_adapter: false,
                install_napcat: false,
                install_mongodb: false,
                install_webui: false
            }
        };
        showModal("", emptyConfig, true);
    });
};

async function showModal(name, data, isNew = false) {
    const modal = document.getElementById("modal");
    const content = document.getElementById("modal-content");
    content.innerHTML = "";
    let editableInstall = false;
    if (!isNew && name) {
        const res = await fetch(`${apiBase}/configs/${name}/uiinfo`).then(r => r.json());
        editableInstall = res.editable_install_options;
    } else if (isNew) {
        editableInstall = true;
    }
    const form = document.createElement("form");
    form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const update = {};
        for (let [k, v] of formData.entries()) {
            if (k.startsWith("install_options_")) {
                const opt = k.replace("install_options_", "");
                if (!update.install_options) update.install_options = {};
                update.install_options[opt] = true;
            } else {
                update[k] = v;
            }
        }
        // 补全未勾选的安装项为false
        if (data.install_options) {
            Object.keys(data.install_options).forEach(opt => {
                if (!update.install_options) update.install_options = {};
                if (!(opt in update.install_options)) update.install_options[opt] = false;
            });
        }
        // 检查名称、序列号、昵称重复
        const configs = await fetch(`${apiBase}/configs`).then(r => r.json());
        const allNames = Object.keys(configs);
        const allSerials = Object.values(configs).map(c => c.serial_number);
        const allNicknames = Object.values(configs).map(c => c.nickname_path);
        let newName = isNew ? formData.get("config_name") : name;
        if (!newName) {
            showMessage("请填写配置集名称", 'error');
            return;
        }
        if ((isNew && allNames.includes(newName)) || (!isNew && newName !== name && allNames.includes(newName))) {
            showMessage("配置集名称已存在", 'error');
            return;
        }
        if (update.serial_number && ((isNew && allSerials.includes(update.serial_number)) || (!isNew && update.serial_number !== configs[name]?.serial_number && allSerials.includes(update.serial_number)))) {
            showMessage("用户序列号已存在", 'error');
            return;
        }
        if (update.nickname_path && ((isNew && allNicknames.includes(update.nickname_path)) || (!isNew && update.nickname_path !== configs[name]?.nickname_path && allNicknames.includes(update.nickname_path)))) {
            showMessage("实例昵称已存在", 'error');
            return;
        }
        // 路径字段校验（只要填写了就校验）
        const pathFields = ["mai_path","adapter_path","napcat_path","venv_path","mongodb_path","webui_path"];
        for (const pf of pathFields) {
            if (update[pf]) {
                // 后端会二次校验，这里只做简单校验
                if (!/^[a-zA-Z]:\\|^\\\\|^\//.test(update[pf])) {
                    showMessage(`${fieldLabels[pf]||pf} 路径格式不正确`, 'error');
                    return;
                }
            }
        }
        // 提交
        if (isNew) {
            fetch(`${apiBase}/configs`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: newName, config: update })
            }).then(r => r.json()).then(res => {
                if (res.success) {
                    modal.classList.remove("show");
                    loadConfigs();
                    showMessage("新建成功", 'success');
                } else {
                    showMessage("新建失败: " + (res.msg || ""), 'error');
                }
            });
        } else {
            fetch(`${apiBase}/configs/${name}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(update)
            }).then(r => r.json()).then(res => {
                if (res.success) {
                    modal.classList.remove("show");
                    loadConfigs();
                    showMessage("保存成功", 'success');
                } else {
                    showMessage("保存失败: " + (res.msg || ""), 'error');
                }
            });
        }
    };
    if (isNew) {
        const row = document.createElement("div");
        row.className = "form-row";
        row.innerHTML = `<label>配置集名称</label>
            <input name="config_name" required placeholder="如：my_config"/>`;
        form.appendChild(row);
    }
    for (let [k, v] of Object.entries(data)) {
        if (typeof v === "object" && v !== null) continue;
        const row = document.createElement("div");
        row.className = "form-row";
        let label = fieldLabels[k] || k;
        let readonly = "";
        if (k === "absolute_serial_number") readonly = "readonly";
        row.innerHTML = `<label>${label}</label>
            <input name="${k}" value="${v ?? ""}" ${readonly}/>`;
        form.appendChild(row);
    }
    // 安装项
    if (data.install_options) {
        const div = document.createElement("div");
        div.className = "install-options";
        div.innerHTML = "<b>安装选项" + (editableInstall ? "" : "（只读）") + "</b><br>";
        Object.entries(data.install_options).forEach(([k, v]) => {
            if (editableInstall) {
                div.innerHTML += `
                    <label style="margin-right:12px;">
                        <input type="checkbox" name="install_options_${k}" ${v ? "checked" : ""}/>
                        ${k}
                    </label>
                `;
            } else {
                div.innerHTML += `${k}: ${v}<br>`;
            }
        });
        form.appendChild(div);
    }
    const actions = document.createElement("div");
    actions.className = "modal-actions";
    actions.innerHTML = `
        <button type="button" class="btn cancel">取消</button>
        ${!isNew ? `<button type="button" class="btn btn-delete" style="background:#e74c3c;">删除</button>` : ""}
        <button type="submit" class="btn">${isNew ? "新建" : "保存"}</button>
    `;
    actions.querySelector(".cancel").onclick = () => modal.classList.remove("show");
    if (!isNew) {
        actions.querySelector(".btn-delete").onclick = () => {
            if (confirm(`确定要删除配置集 "${name}" 吗？`)) {
                fetch(`${apiBase}/configs/${name}`, { method: "DELETE" })
                    .then(r => r.json()).then(res => {
                        if (res.success) {
                            modal.classList.remove("show");
                            loadConfigs();
                            showMessage("删除成功", 'success');
                        } else {
                            showMessage("删除失败: " + (res.msg || ""), 'error');
                        }
                    });
            }
        };
    }
    form.appendChild(actions);

    content.appendChild(form);
    modal.classList.add("show");
}

function loadConfigs() {
    fetch(`${apiBase}/configs`).then(r => r.json()).then(renderConfigs);
}

function applyTheme(theme) {
    if (theme === "auto") {
        const mq = window.matchMedia('(prefers-color-scheme: dark)');
        document.documentElement.setAttribute("data-theme", mq.matches ? "dark" : "light");
    } else {
        document.documentElement.setAttribute("data-theme", theme);
    }
}
async function saveThemeToServer(theme) {
    await fetch(`${apiBase}/ui_settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme })
    });
}
async function loadThemeFromServer() {
    const res = await fetch(`${apiBase}/ui_settings`).then(r => r.json());
    return res.theme || "auto";
}

function saveTheme(theme) {
    localStorage.setItem("theme-mode", theme);
    saveThemeToServer(theme);
}
function loadTheme() {
    return localStorage.getItem("theme-mode") || "auto";
}

window.onload = async () => {
    loadConfigs();
    // 点击遮罩关闭
    document.getElementById("modal").onclick = e => {
        if (e.target === e.currentTarget) e.currentTarget.classList.remove("show");
    };
    // 只保留这一行，绑定自定义设置弹窗
    document.getElementById("settings-btn").onclick = showSettingsModal;

    // 主题初始化（优先从后端加载）
    let serverTheme = await loadThemeFromServer();
    applyTheme(serverTheme);
    saveTheme(serverTheme);
    // 跟随系统变化
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (loadTheme() === "auto") applyTheme("auto");
    });

    // 与后端握手成功消息
    try {
        const uiSettings = await fetch(`${apiBase}/ui_settings`).then(r => r.json());
        showMessage(`成功链接到后端服务器端口${location.port}`, 'success', 2500);
    } catch {
        showMessage('无法连接到后端服务器', 'error', 3500);
    }
};

function showSettingsModal() {
    const modal = document.getElementById("modal");
    const content = document.getElementById("modal-content");
    fetch(`${apiBase}/ui_settings`).then(res => res.json()).then(uiSettings => {
        const currentPort = uiSettings.port || 8000;
        const currentTheme = uiSettings.theme || 'auto';
        
        // 获取代理配置
        fetch(`${apiBase}/proxy`).then(res => res.json()).then(proxyRes => {
            const proxyData = proxyRes.success ? proxyRes.data : {
                enabled: false,
                type: 'http',
                host: '',
                port: '',
                username: '',
                has_password: false,
                exclude_hosts: 'localhost,127.0.0.1'
            };
            
            content.innerHTML = `
                <h2 style="margin-top:0;">设置</h2>
                <div class="form-row" style="padding-left:16px;padding-right:16px;">
                    <label style="width:120px;">主题模式</label>
                    <select id="theme-select-modal" class="btn" style="min-width:120px;">
                        <option value="auto">跟随系统</option>
                        <option value="light">明亮</option>
                        <option value="dark">暗色</option>
                    </select>
                </div>
                
                <!-- 网络代理设置 -->
                <details id="proxy-settings" style="margin-top:18px;padding-left:8px;padding-right:8px;">
                    <summary style="font-size:16px;cursor:pointer;padding-left:8px;padding-right:8px;">🌐 网络代理设置</summary>
                    <div style="padding:16px;">
                        <div class="form-row" style="margin-bottom:12px;">
                            <label style="width:120px;">
                                <input type="checkbox" id="proxy-enabled" ${proxyData.enabled ? 'checked' : ''}/>
                                启用代理
                            </label>
                        </div>
                        
                        <div id="proxy-config-panel" style="${proxyData.enabled ? '' : 'display:none;'}">
                            <div class="form-row" style="margin-bottom:12px;">
                                <label style="width:120px;">代理类型</label>
                                <select id="proxy-type" class="btn" style="min-width:120px;">
                                    <option value="http" ${proxyData.type === 'http' ? 'selected' : ''}>HTTP</option>
                                    <option value="https" ${proxyData.type === 'https' ? 'selected' : ''}>HTTPS</option>
                                    <option value="socks5" ${proxyData.type === 'socks5' ? 'selected' : ''}>SOCKS5</option>
                                    <option value="socks4" ${proxyData.type === 'socks4' ? 'selected' : ''}>SOCKS4</option>
                                </select>
                            </div>
                            
                            <div class="form-row" style="margin-bottom:12px;">
                                <label style="width:120px;">代理主机</label>
                                <input id="proxy-host" type="text" placeholder="例如: 127.0.0.1" value="${proxyData.host}" style="flex:1;padding-left:12px;"/>
                            </div>
                            
                            <div class="form-row" style="margin-bottom:12px;">
                                <label style="width:120px;">代理端口</label>
                                <input id="proxy-port" type="number" min="1" max="65535" placeholder="例如: 7890" value="${proxyData.port}" style="flex:1;padding-left:12px;"/>
                            </div>
                            
                            <div class="form-row" style="margin-bottom:12px;">
                                <label style="width:120px;">用户名</label>
                                <input id="proxy-username" type="text" placeholder="可选" value="${proxyData.username}" style="flex:1;padding-left:12px;"/>
                            </div>
                            
                            <div class="form-row" style="margin-bottom:12px;">
                                <label style="width:120px;">密码</label>
                                <input id="proxy-password" type="password" placeholder="可选" style="flex:1;padding-left:12px;"/>
                            </div>
                            
                            <div class="form-row" style="margin-bottom:12px;">
                                <label style="width:120px;">排除主机</label>
                                <input id="proxy-exclude" type="text" placeholder="用逗号分隔" value="${proxyData.exclude_hosts}" style="flex:1;padding-left:12px;"/>
                            </div>
                            <div style="color:#888;font-size:13px;margin-left:136px;margin-top:-8px;margin-bottom:12px;">
                                不使用代理的主机列表，用逗号分隔
                            </div>
                            
                            <div style="text-align:right;margin-top:12px;">
                                <button type="button" class="btn" id="test-proxy-btn" style="background:#4CAF50;color:white;padding:8px 16px;">
                                    测试连接
                                </button>
                            </div>
                            <div id="proxy-test-result" style="margin-top:12px;padding:8px;border-radius:4px;display:none;"></div>
                        </div>
                    </div>
                </details>
                
                <details id="advanced-settings" style="margin-top:18px;padding-left:8px;padding-right:8px;">
                    <summary style="font-size:16px;cursor:pointer;padding-left:8px;padding-right:8px;">高级设置</summary>
                    <div class="form-row" style="margin-top:16px;padding-left:16px;padding-right:16px;">
                        <label style="width:120px;">通信端口</label>
                        <input id="port-input" type="number" min="1" max="65535" style="flex:1;margin-right:12px;padding-left:12px;" value="${currentPort}"/>
                    </div>
                    <div style="color:#888;font-size:13px;margin-left:136px;margin-top:4px;">修改端口后需重启服务生效</div>
                </details>
                <div class="modal-actions" style="padding-left:16px;padding-right:16px;">
                    <button type="button" class="btn cancel">关闭</button>
                    <button type="button" class="btn" id="save-settings-btn">保存设置</button>
                </div>
            `;
            
            // 代理启用/禁用切换
            const proxyEnabled = content.querySelector("#proxy-enabled");
            const proxyPanel = content.querySelector("#proxy-config-panel");
            proxyEnabled.onchange = () => {
                proxyPanel.style.display = proxyEnabled.checked ? '' : 'none';
            };
            
            // 测试代理连接
            content.querySelector("#test-proxy-btn").onclick = async () => {
                const testBtn = content.querySelector("#test-proxy-btn");
                const resultDiv = content.querySelector("#proxy-test-result");
                
                testBtn.disabled = true;
                testBtn.textContent = "测试中...";
                resultDiv.style.display = 'block';
                resultDiv.style.background = '#f0f0f0';
                resultDiv.style.color = '#333';
                resultDiv.textContent = '正在测试代理连接...';
                
                try {
                    const response = await fetch(`${apiBase}/proxy/test`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ test_url: 'https://www.baidu.com' })
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        resultDiv.style.background = '#d4edda';
                        resultDiv.style.color = '#155724';
                        resultDiv.textContent = '✓ ' + result.message;
                    } else {
                        resultDiv.style.background = '#f8d7da';
                        resultDiv.style.color = '#721c24';
                        resultDiv.textContent = '✗ ' + result.message;
                    }
                } catch (error) {
                    resultDiv.style.background = '#f8d7da';
                    resultDiv.style.color = '#721c24';
                    resultDiv.textContent = '✗ 测试失败: ' + error.message;
                }
                
                testBtn.disabled = false;
                testBtn.textContent = "测试连接";
            };
            
            // 设置当前主题
            const themeSelect = content.querySelector("#theme-select-modal");
            themeSelect.value = currentTheme;
            themeSelect.onchange = () => {
                applyTheme(themeSelect.value);
                saveTheme(themeSelect.value);
            };
            
            content.querySelector(".cancel").onclick = () => modal.classList.remove("show");
            
            // 保存设置
            content.querySelector("#save-settings-btn").onclick = async () => {
                const port = parseInt(content.querySelector("#port-input").value, 10);
                const theme = themeSelect.value;
                
                // 受限端口列表（主流浏览器限制）
                const unsafePorts = [1,7,9,11,13,15,17,19,20,21,22,23,25,37,42,43,53,77,79,87,95,101,102,103,104,109,110,111,113,115,117,119,123,135,139,143,179,389,427,465,512,513,514,515,526,530,531,532,540,548,556,563,587,601,636,993,995,2049,3659,4045,6000,6665,6666,6667,6668,6669,6697,10080,32768,32769,32770,32771,32772,32773,32774,32775,32776,32777,32778,32779,32780,32781,32782,32783,32784,32785,33354,65535];
                if (unsafePorts.includes(port)) {
                    showMessage("该端口为浏览器受限端口，无法访问，请更换其他端口！\\n建议使用 1024~49151 之间的常用端口，如 2000、3000、5000、8888、9000、23333 等。", 'error', 3500);
                    return;
                }
                
                // 保存代理设置
                if (proxyEnabled.checked) {
                    const proxyHost = content.querySelector("#proxy-host").value.trim();
                    const proxyPort = content.querySelector("#proxy-port").value.trim();
                    
                    if (!proxyHost || !proxyPort) {
                        showMessage("启用代理时必须填写代理主机和端口", 'error');
                        return;
                    }
                }
                
                const proxySettings = {
                    enabled: proxyEnabled.checked,
                    type: content.querySelector("#proxy-type").value,
                    host: content.querySelector("#proxy-host").value.trim(),
                    port: content.querySelector("#proxy-port").value.trim(),
                    username: content.querySelector("#proxy-username").value.trim(),
                    password: content.querySelector("#proxy-password").value.trim(),
                    exclude_hosts: content.querySelector("#proxy-exclude").value.trim()
                };
                
                try {
                    // 保存代理配置
                    const proxyResponse = await fetch(`${apiBase}/proxy`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(proxySettings)
                    });
                    const proxyResult = await proxyResponse.json();
                    
                    if (!proxyResult.success) {
                        showMessage("保存代理设置失败: " + (proxyResult.msg || ""), 'error');
                        return;
                    }
                    
                    // 保存UI设置
                    await fetch(`${apiBase}/ui_settings`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ theme, port })
                    });
                    
                    showMessage("设置已保存成功！", 'success', 3000);
                    modal.classList.remove("show");
                    applyTheme(theme);
                    saveTheme(theme);
                } catch (error) {
                    showMessage("保存设置时出错: " + error.message, 'error');
                }
            };
            
            modal.classList.add("show");
        });
    });
}
