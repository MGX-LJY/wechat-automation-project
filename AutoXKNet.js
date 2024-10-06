// ==UserScript==
// @name         自动下载学科网
// @namespace    http://tampermonkey.net/
// @version      7.6
// @description  自动下载学科网（zxxk.com）的下载按钮和确认按钮，5分钟后自动关闭网页，防止占用内存。添加自动登录功能，当下载次数达到上限时，自动切换账号。新增：如果脚本在20秒内未能正常运行，自动刷新页面，除非发生页面跳转。
// @match        *://*.zxxk.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 配置选择器
    const SELECTORS = {
        downloadBtn: '.download-btn',
        iframe: 'iframe[id^="layui-layer-iframe"]',
        confirmBtn: '.balance-payment-btn',
        errorBox: '.ppt-error-box',
        errorCloseBtn: '.icon-guanbi1',
        limitDialog: '.risk-control-dialog',
        limitConfirmBtn: '.dialog-footer .btn',
        logoutBtn: '.dl-quit',
        loginBtn: '.login-btn',
        username: '#username',
        password: '#password',
        loginSubmit: '#accountLoginBtn',
    };

    // 配置参数
    const CONFIG = {
        clickInterval: 5000, // 毫秒
        errorCheckInterval: 10000, // 毫秒
        maxRetries: 3,
        maxErrorHandling: 5,
        pageCloseDelay: 5 * 60 * 1000, // 5分钟
        scriptTimeout: 20000, // 20秒
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
    };

    /**
     * 通知用户
     * @param {string} message
     */
    const notify = (message) => console.log(`[自动下载学科网]: ${message}`);

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
     * 等待元素出现
     * @param {string} selector
     * @param {number} timeout
     * @returns {Promise<HTMLElement>}
     */
    const waitForElement = (selector, timeout = 10000) => {
        return new Promise((resolve, reject) => {
            const interval = setInterval(() => {
                const el = document.querySelector(selector);
                if (el) {
                    clearInterval(interval);
                    resolve(el);
                }
            }, 500);

            setTimeout(() => {
                clearInterval(interval);
                reject(new Error(`等待超时: ${selector}`));
            }, timeout);
        });
    };

    /**
     * 处理下载流程
     * @param {number} retry
     */
    const processDownload = async (retry = 0) => {
        if (state.downloadStarted) return;

        try {
            const downloadBtn = await waitForElement(SELECTORS.downloadBtn, CONFIG.scriptTimeout);
            clickButton(downloadBtn, '下载按钮');

            const iframe = await waitForElement(SELECTORS.iframe, 10000);
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            const confirmBtn = iframeDoc.querySelector(SELECTORS.confirmBtn);

            if (confirmBtn) {
                clickButton(confirmBtn, '确认按钮');
                state.downloadStarted = true;
                clearTimeout(state.refreshTimeout);
                clearInterval(state.errorCheckInterval);
                clearTimeout(state.closeTimeout);
                notify('下载已启动，准备关闭页面。');
                setTimeout(closePage, CONFIG.clickInterval);
            } else if (retry < CONFIG.maxRetries) {
                notify(`未找到确认按钮，重试(${retry + 1})`);
                setTimeout(() => processDownload(retry + 1), CONFIG.clickInterval);
            } else {
                throw new Error('未找到确认按钮，达到最大重试次数。');
            }
        } catch (error) {
            notify(`下载流程错误: ${error.message}`);
        }
    };

    /**
     * 处理错误提示框
     */
    const handleError = () => {
        if (state.downloadStarted) return;

        const limitDialog = document.querySelector(SELECTORS.limitDialog);
        if (limitDialog && limitDialog.style.display !== 'none') {
            const limitConfirm = limitDialog.querySelector(SELECTORS.limitConfirmBtn);
            if (limitConfirm) {
                clickButton(limitConfirm, '下载次数上限提示框确认按钮');
                switchAccount();
            }
            return;
        }

        const errorBoxes = document.querySelectorAll(SELECTORS.errorBox);
        errorBoxes.forEach(box => {
            if (box.style.display !== 'none') {
                const closeBtn = box.querySelector(SELECTORS.errorCloseBtn);
                if (closeBtn) {
                    closeBtn.click();
                    state.errorCount++;
                    notify('已关闭错误提示框。');
                }
            }
        });

        if (state.errorCount < CONFIG.maxErrorHandling) {
            notify('尝试重新下载。');
            processDownload();
        } else {
            notify('达到最大错误处理次数，停止操作。');
            clearInterval(state.errorCheckInterval);
        }
    };

    /**
     * 切换账号
     */
    const switchAccount = async () => {
        notify('切换账号。');

        const logoutBtn = document.querySelector(SELECTORS.logoutBtn);
        if (logoutBtn) {
            clickButton(logoutBtn, '退出按钮');
            await new Promise(res => setTimeout(res, CONFIG.clickInterval));
        }

        const loginBtn = document.querySelector(SELECTORS.loginBtn);
        if (loginBtn) {
            clickButton(loginBtn, '登录按钮');
            await new Promise(res => setTimeout(res, CONFIG.clickInterval));
            await fillLoginForm();
        } else {
            notify('未找到登录按钮。');
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

        const usernameInput = document.querySelector(SELECTORS.username);
        const passwordInput = document.querySelector(SELECTORS.password);
        const loginSubmit = document.querySelector(SELECTORS.loginSubmit);

        if (usernameInput && passwordInput && loginSubmit) {
            usernameInput.value = account.username;
            passwordInput.value = account.password;
            clickButton(loginSubmit, '登录提交按钮');
            notify(`已尝试使用账号 ${account.username} 登录。`);
            state.accountIndex = (state.accountIndex + 1) % accounts.length;
            await new Promise(res => setTimeout(res, CONFIG.clickInterval));
            processDownload();
        } else {
            notify('登录表单元素未找到。');
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
    const init = () => {
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
        processDownload();

        // 设置错误处理间隔
        state.errorCheckInterval = setInterval(handleError, CONFIG.errorCheckInterval);

        // 设置刷新超时，只有未发生跳转时才会刷新
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
