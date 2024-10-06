// ==UserScript==
// @name         自动下载学科网 - 高容错版
// @namespace    http://tampermonkey.net/
// @version      7.7
// @description  自动下载学科网（zxxk.com）的下载按钮和确认按钮，5分钟后自动关闭网页，防止占用内存。添加自动登录功能，当下载次数达到上限时，自动切换账号。新增：如果脚本在20秒内未能正常运行，自动刷新页面，除非发生页面跳转。增强容错能力。
// @match        *://*.zxxk.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 配置选择器
    const SELECTORS = {
        downloadBtn: ['.download-btn', '.btn-download'], // 备用选择器
        iframe: 'iframe[id^="layui-layer-iframe"]',
        confirmBtn: ['.balance-payment-btn', '.btn-confirm'], // 备用选择器
        errorBox: ['.ppt-error-box', '.error-box'], // 备用选择器
        errorCloseBtn: ['.icon-guanbi1', '.btn-close'], // 备用选择器
        limitDialog: ['.risk-control-dialog', '.limit-dialog'], // 备用选择器
        limitConfirmBtn: ['.dialog-footer .btn', '.btn-confirm-limit'], // 备用选择器
        logoutBtn: ['.dl-quit', '.btn-logout'], // 备用选择器
        loginBtn: ['.login-btn', '.btn-login'], // 备用选择器
        username: ['#username', 'input[name="username"]'], // 备用选择器
        password: ['#password', 'input[name="password"]'], // 备用选择器
        loginSubmit: ['#accountLoginBtn', '.btn-login-submit'], // 备用选择器
    };

    // 配置参数
    const CONFIG = {
        clickInterval: 5000, // 毫秒
        errorCheckInterval: 10000, // 毫秒
        maxRetries: 5, // 增加最大重试次数
        maxErrorHandling: 10, // 增加最大错误处理次数
        pageCloseDelay: 5 * 60 * 1000, // 5分钟
        scriptTimeout: 20000, // 20秒
        exponentialBackoffBase: 2, // 指数退避基数
        maxBackoffTime: 60000, // 最大退避时间 60秒
    };

    // 账号列表（请在这里填写您的账号信息）
    const accounts = [
        { username: '13143019361', password: '428199Li@' },
        { username: '19061531853', password: '428199Li@' },
        { username: '16600076291', password: '428199Li@' },
        { username: '15512733826', password: '428199Li@' },
    ];

    let state = {
        errorCount: 0,
        downloadStarted: false,
        accountIndex: 0,
        refreshTimeout: null,
        closeTimeout: null,
        errorCheckInterval: null,
        redirected: false, // 标志是否发生了跳转
        retryCount: 0,
        observer: null,
    };

    /**
     * 通知用户
     * @param {string} message
     */
    const notify = (message) => {
        console.log(`[自动下载学科网]: ${message}`);
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('自动下载学科网', { body: message });
        }
    };

    /**
     * 统一的跳转函数，设置跳转标志并执行跳转
     * @param {string} url
     */
    const redirectTo = (url) => {
        notify(`正在跳转到: ${url}`);
        state.redirected = true;
        window.location.href = url;
    };

    /**
     * 获取元素，支持备用选择器
     * @param {Array<string>} selectors
     * @returns {HTMLElement|null}
     */
    const getElement = (selectors) => {
        for (let selector of selectors) {
            const el = document.querySelector(selector);
            if (el) return el;
        }
        return null;
    };

    /**
     * 点击按钮
     * @param {HTMLElement} button
     * @param {string} type
     */
    const clickButton = (button, type) => {
        if (button && !button.dataset.clicked) {
            button.click();
            button.dataset.clicked = 'true';
            notify(`${type}已点击。`);
        }
    };

    /**
     * 等待元素出现，支持备用选择器
     * 使用MutationObserver监听DOM变化，提高效率
     * @param {Array<string>} selectors
     * @param {number} timeout
     * @returns {Promise<HTMLElement>}
     */
    const waitForElement = (selectors, timeout = 10000) => {
        return new Promise((resolve, reject) => {
            const element = getElement(selectors);
            if (element) {
                return resolve(element);
            }

            const observer = new MutationObserver((mutations, obs) => {
                const el = getElement(selectors);
                if (el) {
                    obs.disconnect();
                    resolve(el);
                }
            });

            observer.observe(document.body, { childList: true, subtree: true });

            setTimeout(() => {
                observer.disconnect();
                reject(new Error(`等待超时: ${selectors.join(' 或 ')} 没有找到`));
            }, timeout);
        });
    };

    /**
     * 延迟函数
     * @param {number} ms
     * @returns {Promise}
     */
    const delay = (ms) => new Promise(res => setTimeout(res, ms));

    /**
     * 处理下载流程
     * @param {number} retry
     */
    const processDownload = async (retry = 0) => {
        if (state.downloadStarted) return;

        try {
            notify('尝试查找下载按钮...');
            const downloadBtn = await waitForElement(SELECTORS.downloadBtn, CONFIG.scriptTimeout);
            clickButton(downloadBtn, '下载按钮');

            notify('尝试查找下载确认框的iframe...');
            const iframe = await waitForElement([SELECTORS.iframe], CONFIG.scriptTimeout);
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

            notify('尝试查找确认按钮...');
            const confirmBtn = getElement(SELECTORS.confirmBtn);

            if (confirmBtn) {
                clickButton(confirmBtn, '确认按钮');
                state.downloadStarted = true;
                clearTimeout(state.refreshTimeout);
                clearInterval(state.errorCheckInterval);
                clearTimeout(state.closeTimeout);
                notify('下载已启动，准备关闭页面。');
                setTimeout(closePage, CONFIG.clickInterval);
            } else if (retry < CONFIG.maxRetries) {
                const backoffTime = Math.min(CONFIG.exponentialBackoffBase ** retry * 1000, CONFIG.maxBackoffTime);
                notify(`未找到确认按钮，${retry + 1}次重试将在 ${backoffTime / 1000} 秒后进行`);
                await delay(backoffTime);
                processDownload(retry + 1);
            } else {
                throw new Error('未找到确认按钮，达到最大重试次数。');
            }
        } catch (error) {
            notify(`下载流程错误: ${error.message}`);
            handleError();
        }
    };

    /**
     * 处理错误提示框
     */
    const handleError = async () => {
        if (state.downloadStarted) return;

        try {
            const limitDialog = getElement(SELECTORS.limitDialog);
            if (limitDialog && limitDialog.style.display !== 'none') {
                const limitConfirm = getElement(SELECTORS.limitConfirmBtn);
                if (limitConfirm) {
                    clickButton(limitConfirm, '下载次数上限提示框确认按钮');
                    await switchAccount();
                }
                return;
            }

            const errorBoxes = document.querySelectorAll(SELECTORS.errorBox.join(','));
            for (let box of errorBoxes) {
                if (box.style.display !== 'none') {
                    const closeBtn = getElement(SELECTORS.errorCloseBtn);
                    if (closeBtn) {
                        closeBtn.click();
                        state.errorCount++;
                        notify('已关闭错误提示框。');
                    }
                }
            }

            if (state.errorCount < CONFIG.maxErrorHandling) {
                notify('尝试重新下载...');
                await processDownload();
            } else {
                notify('达到最大错误处理次数，停止操作。');
                clearInterval(state.errorCheckInterval);
            }
        } catch (error) {
            notify(`处理错误提示框时发生错误: ${error.message}`);
        }
    };

    /**
     * 切换账号
     */
    const switchAccount = async () => {
        notify('切换账号。');

        try {
            const logoutBtn = getElement(SELECTORS.logoutBtn);
            if (logoutBtn) {
                clickButton(logoutBtn, '退出按钮');
                await delay(CONFIG.clickInterval);
            }

            const loginBtn = getElement(SELECTORS.loginBtn);
            if (loginBtn) {
                clickButton(loginBtn, '登录按钮');
                await delay(CONFIG.clickInterval);
                await fillLoginForm();
            } else {
                throw new Error('未找到登录按钮。');
            }
        } catch (error) {
            notify(`切换账号时发生错误: ${error.message}`);
        }
    };

    /**
     * 填写并提交登录表单
     */
    const fillLoginForm = async () => {
        const account = accounts[state.accountIndex];
        if (!account) {
            notify('没有更多账号可供切换。');
            return;
        }

        try {
            notify(`尝试使用账号 ${account.username} 登录。`);

            const usernameInput = getElement(SELECTORS.username);
            const passwordInput = getElement(SELECTORS.password);
            const loginSubmit = getElement(SELECTORS.loginSubmit);

            if (usernameInput && passwordInput && loginSubmit) {
                usernameInput.value = account.username;
                passwordInput.value = account.password;
                clickButton(loginSubmit, '登录提交按钮');
                state.accountIndex = (state.accountIndex + 1) % accounts.length;
                await delay(CONFIG.clickInterval * 2);
                await processDownload();
            } else {
                throw new Error('登录表单元素未找到。');
            }
        } catch (error) {
            notify(`填写登录表单时发生错误: ${error.message}`);
        }
    };

    /**
     * 尝试关闭页面
     */
    const closePage = () => {
        notify('尝试关闭页面。');
        window.close();
        setTimeout(() => {
            if (!window.closed) {
                redirectTo('about:blank');
            }
        }, 1000);
    };

    /**
     * 初始化脚本
     */
    const init = async () => {
        try {
            // 检查当前是否在移动端
            if (window.location.hostname === "m.zxxk.com") {
                const currentPath = window.location.pathname; // 例如: /soft/42922760.html
                const softidMatch = currentPath.match(/\/soft\/(\d+)\.html/);
                if (softidMatch) {
                    const softid = softidMatch[1];
                    const desktopUrl = `https://www.zxxk.com/soft/softdownload?softid=${softid}`;
                    redirectTo(desktopUrl);
                    return; // 跳转后停止执行后续脚本
                }
            }

            // 开始下载流程
            await processDownload();

            // 设置错误处理间隔
            state.errorCheckInterval = setInterval(handleError, CONFIG.errorCheckInterval);

            // 设置刷新超时，只有未发生跳转且未启动下载时才会刷新
            state.refreshTimeout = setTimeout(() => {
                if (!state.downloadStarted && !state.redirected) {
                    notify('脚本未能在20秒内正常运行，刷新页面。');
                    window.location.reload();
                }
            }, CONFIG.scriptTimeout);

            // 设置页面关闭定时器
            state.closeTimeout = setTimeout(() => {
                notify('5分钟已到，自动关闭网页以防止占用内存。');
                closePage();
            }, CONFIG.pageCloseDelay);
        } catch (error) {
            notify(`初始化脚本时发生错误: ${error.message}`);
        }
    };

    // 请求通知权限
    if (typeof Notification !== 'undefined') {
        if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    }

    // 监听页面加载完成后执行
    window.addEventListener('load', () => {
        if (window.self === window.top) {
            init();
        }
    });

})();
