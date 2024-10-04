// ==UserScript==
// @name         自动下载学科网
// @namespace    http://tampermonkey.net/
// @version      7.3
// @description  自动下载学科网（zxxk.com）的下载按钮和确认按钮，5分钟后自动关闭网页，防止占用内存。
// @match        *://*.zxxk.com/*
// @require      https://raw.githubusercontent.com/MGX-LJY/wechat-automation-project/refs/heads/main/AutoXKNet.js
// @updateURL    https://raw.githubusercontent.com/MGX-LJY/wechat-automation-project/refs/heads/main/AutoXKNet.js
// @downloadURL  https://raw.githubusercontent.com/MGX-LJY/wechat-automation-project/refs/heads/main/AutoXKNet.js
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 配置选择器
    const DOWNLOAD_BUTTON_SELECTOR = '.download-btn'; // 下载按钮的类名
    const IFRAME_SELECTOR = 'iframe[id^="layui-layer-iframe"]'; // 弹窗的 iframe 选择器
    const CONFIRM_BUTTON_SELECTOR = '.balance-payment-btn'; // 确认按钮的类名
    const ERROR_BOX_SELECTOR = '.ppt-error-box'; // 错误提示框的类名
    const ERROR_CLOSE_BUTTON_SELECTOR = '.icon-guanbi1'; // 错误提示框中关闭按钮的类名

    // 配置参数
    const CLICK_INTERVAL = 5000; // 每个按钮点击的间隔时间（毫秒）
    const ERROR_CHECK_INTERVAL = 10000; // 错误提示框检查的间隔时间（毫秒）
    const MAX_RETRIES = 3; // 按钮点击最大重试次数
    const MAX_ERROR_HANDLING = 5; // 最大错误处理次数
    const PAGE_CLOSE_DELAY = 5 * 60 * 1000; // 5分钟后关闭页面

    let errorHandlingCount = 0; // 当前错误处理次数
    let downloadStarted = false; // 标记是否已成功启动下载
    let errorCheckIntervalId = null; // 错误检查的定时器ID
    let pageCloseTimeoutId = null; // 页面关闭的定时器ID

    /**
     * 通知用户
     * @param {string} message - 要显示的消息
     */
    function notifyUser(message) {
        if (Notification.permission === 'granted') {
            new Notification(message);
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    new Notification(message);
                }
            });
        }
    }

    /**
     * 点击指定的按钮
     * @param {HTMLElement} button - 需要点击的按钮
     * @param {string} buttonType - 按钮类型（用于日志和通知）
     * @param {Function} callback - 点击完成后的回调函数
     */
    function clickButton(button, buttonType = '按钮', callback) {
        if (!button || button.dataset.clicked) {
            callback && callback();
            return;
        }

        console.log(`正在点击${buttonType}:`, button);

        try {
            button.click();
            button.dataset.clicked = 'true'; // 标记已点击，防止重复点击
            notifyUser(`${buttonType}已点击。`);
        } catch (error) {
            console.error(`点击${buttonType}失败:`, error);
            callback && callback(error);
            return;
        }

        // 等待一段时间，模拟人工操作
        const delay = CLICK_INTERVAL + Math.random() * 2000; // 随机延迟
        setTimeout(() => {
            callback && callback();
        }, delay);
    }

    /**
     * 处理下载流程
     */
    function processDownload(retryCount = 0) {
        if (downloadStarted) {
            console.log('下载已启动，停止进一步下载尝试。');
            return;
        }

        const downloadButton = document.querySelector(DOWNLOAD_BUTTON_SELECTOR);
        if (!downloadButton) {
            console.log('未找到下载按钮。请检查选择器是否正确。');
            return;
        }

        clickButton(downloadButton, '下载按钮', (error) => {
            if (error) return;

            // 等待 iframe 出现并加载完成
            waitForIframeLoad(IFRAME_SELECTOR, 10000)
                .then((iframe) => {
                    handleIframe(iframe, retryCount);
                })
                .catch(() => {
                    console.log('未找到弹窗 iframe，下载流程结束。');
                    // 可能下载已启动，尝试检测下载是否成功
                    // 这里可以添加额外的检测逻辑
                });
        });
    }

    /**
     * 处理 iframe 内部的确认按钮
     * @param {HTMLIFrameElement} iframe - 需要处理的 iframe
     * @param {number} retryCount - 当前重试次数
     */
    function handleIframe(iframe, retryCount) {
        try {
            const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
            if (!iframeDocument) throw new Error('无法访问 iframe 内部的文档。');

            const confirmButton = iframeDocument.querySelector(CONFIRM_BUTTON_SELECTOR);
            if (confirmButton) {
                clickButton(confirmButton, '确认按钮', () => {
                    console.log('确认按钮已点击，下载流程完成。');
                    downloadStarted = true; // 标记下载已启动

                    // 取消错误检查和页面关闭的定时器
                    if (errorCheckIntervalId) {
                        clearInterval(errorCheckIntervalId);
                        errorCheckIntervalId = null;
                    }
                    if (pageCloseTimeoutId) {
                        clearTimeout(pageCloseTimeoutId);
                        pageCloseTimeoutId = null;
                    }

                    // 关闭页面（如果需要）
                    setTimeout(() => {
                        console.log('下载已启动，准备关闭页面。');
                        tryCloseWindow();
                    }, CLICK_INTERVAL);
                });
            } else {
                console.log('iframe 内未找到确认按钮。');
                // 如果未找到确认按钮，尝试再次处理
                if (retryCount < MAX_RETRIES) {
                    console.log(`重试处理 iframe，剩余重试次数：${MAX_RETRIES - retryCount}`);
                    setTimeout(() => {
                        handleIframe(iframe, retryCount + 1);
                    }, CLICK_INTERVAL);
                } else {
                    console.log('已达到最大重试次数，停止处理。');
                }
            }
        } catch (e) {
            console.error('处理 iframe 时发生错误：', e);
            // 如果是跨域问题，无法访问 iframe 内容，可能需要其他方法
            if (e.name === 'SecurityError') {
                console.error('无法访问跨域的 iframe。');
            }
            if (retryCount < MAX_RETRIES) {
                console.log(`重试处理 iframe，剩余重试次数：${MAX_RETRIES - retryCount}`);
                setTimeout(() => {
                    handleIframe(iframe, retryCount + 1);
                }, CLICK_INTERVAL);
            } else {
                console.log('已达到最大重试次数，停止处理。');
            }
        }
    }

    /**
     * 等待 iframe 出现并加载完成
     * @param {string} selector - iframe 选择器
     * @param {number} timeout - 超时时间（毫秒）
     * @returns {Promise<HTMLIFrameElement>}
     */
    function waitForIframeLoad(selector, timeout = 10000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();

            function check() {
                const iframes = document.querySelectorAll(selector);
                const targetIframe = Array.from(iframes).find(iframe => !iframe.dataset.processed);

                if (targetIframe) {
                    // 等待 iframe 加载完成
                    if (targetIframe.contentDocument || targetIframe.contentWindow.document) {
                        targetIframe.dataset.processed = 'true'; // 标记为已处理
                        resolve(targetIframe);
                    } else {
                        targetIframe.addEventListener('load', () => {
                            targetIframe.dataset.processed = 'true'; // 标记为已处理
                            resolve(targetIframe);
                        });
                    }
                } else if (Date.now() - startTime >= timeout) {
                    reject();
                } else {
                    requestAnimationFrame(check);
                }
            }

            check();
        });
    }

    /**
     * 检查并处理错误提示框
     */
    function checkAndHandleErrorBox() {
        if (downloadStarted) {
            console.log('下载已启动，停止错误检查。');
            if (errorCheckIntervalId) {
                clearInterval(errorCheckIntervalId);
                errorCheckIntervalId = null;
            }
            return;
        }

        const errorBoxes = document.querySelectorAll(ERROR_BOX_SELECTOR);
        if (errorBoxes.length === 0) return;

        errorBoxes.forEach((errorBox) => {
            if (errorBox.style.display !== 'none') {
                console.log('检测到加载错误，尝试关闭错误提示框。');
                const closeButton = errorBox.querySelector(ERROR_CLOSE_BUTTON_SELECTOR);
                if (closeButton) {
                    closeButton.click();
                    errorHandlingCount++;
                    console.log('已关闭错误提示框。');
                }
            }
        });

        if (errorHandlingCount < MAX_ERROR_HANDLING) {
            // 等待一段时间后重新尝试下载
            console.log('尝试重新下载。');
            setTimeout(processDownload, CLICK_INTERVAL + Math.random() * 2000);
        } else {
            console.log('已达到最大错误处理次数，停止进一步操作。');
            if (errorCheckIntervalId) {
                clearInterval(errorCheckIntervalId);
                errorCheckIntervalId = null;
            }
        }
    }

    /**
     * 尝试关闭窗口，处理不同浏览器的兼容性
     */
    function tryCloseWindow() {
        console.log('尝试关闭窗口。');
        window.open('', '_self', '');
        window.close();

        // 检查窗口是否成功关闭
        setTimeout(() => {
            if (!window.closed) {
                console.log('无法自动关闭窗口，尝试替代方案。');
                window.location.href = 'about:blank';
            }
        }, 1000);
    }

    // 请求浏览器通知权限
    if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
        Notification.requestPermission();
    }

    // 监听页面加载完成后执行初始操作
    window.addEventListener('load', function() {
        if (window.self === window.top) {
            processDownload();
            errorCheckIntervalId = setInterval(checkAndHandleErrorBox, ERROR_CHECK_INTERVAL);
            pageCloseTimeoutId = setTimeout(() => {
                console.log('5分钟已到，自动关闭网页以防止占用内存。');
                tryCloseWindow();
            }, PAGE_CLOSE_DELAY);
        }
    }, false);
})();
