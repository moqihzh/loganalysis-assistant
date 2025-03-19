$(document).ready(function() {
    // 刷新验证码
    function refreshCaptcha() {
        const timestamp = new Date().getTime();
        $('#captchaImage').attr('src', '/api/captcha?' + timestamp);
    }

    // 点击验证码图片时刷新
    $('#captchaImage').click(function() {
        refreshCaptcha();
    });

    // 清除表单错误提示
    function clearError(element) {
        const formGroup = $(element).closest('.form-group');
        formGroup.find('.error-message').remove();
        $(element).css('border-color', '#d9d9d9');
    }

    // 显示错误提示
    function showError(element, message) {
        const formGroup = $(element).closest('.form-group');
        clearError(element);
        formGroup.append(`<div class="error-message">${message}</div>`);
        $(element).css('border-color', '#ff4d4f');
    }

    // 表单提交处理
    $('#loginForm').on('submit', function(e) {
        e.preventDefault();
        
        // 清除所有错误提示
        $('.error-message').remove();
        $('input').css('border-color', '#d9d9d9');

        // 获取表单数据
        const username = $('#username').val().trim();
        const password = $('#password').val();
        const captcha = $('#captcha').val().trim();

        // 表单验证
        let hasError = false;
        if (!username) {
            showError('#username', '请输入用户名');
            hasError = true;
        }
        if (!password) {
            showError('#password', '请输入密码');
            hasError = true;
        }
        if (!captcha) {
            showError('#captcha', '请输入验证码');
            hasError = true;
        }

        if (hasError) return;

        // 设置按钮加载状态
        const $submitBtn = $('.login-btn');
        $submitBtn.addClass('loading');

        // 发送登录请求
        $.ajax({
            url: '/api/login',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                username: username,
                password: password,
                captcha: captcha
            }),
            success: function(response) {
                // 登录成功，跳转到首页
                window.location.href = '/';
            },
            error: function(xhr) {
                // 登录失败处理
                const response = xhr.responseJSON || {};
                const message = response.message || '登录失败，请重试';
                
                if (response.code === 'INVALID_CAPTCHA') {
                    showError('#captcha', message);
                    refreshCaptcha();
                    $('#captcha').val('');
                } else if (response.code === 'INVALID_CREDENTIALS') {
                    showError('#password', message);
                    $('#password').val('');
                } else {
                    showError('#username', message);
                }
            },
            complete: function() {
                // 移除按钮加载状态
                $submitBtn.removeClass('loading');
            }
        });
    });

    // 输入框获得焦点时清除错误提示
    $('input').on('focus', function() {
        clearError(this);
    });
});