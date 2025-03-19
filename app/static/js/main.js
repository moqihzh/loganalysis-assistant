$(document).ready(function() {
    let currentPage = 1;
    let pageSize = 10;
    let isTaskRunning = false;
    let totalPages = 1;

    // 显示错误详情模态框
    function showErrorModal(errorMessage) {
        $('.modal-body').text(errorMessage);
        $('#errorModal').css('display', 'block');
    }

    // 关闭模态框
    function closeModal() {
        $('#errorModal').css('display', 'none');
    }

    // 绑定关闭按钮事件
    $('.close-button').click(closeModal);

    // 点击模态框外部关闭
    $(window).click(function(event) {
        if ($(event.target).is('#errorModal')) {
            closeModal();
        }
    });

    // 更新任务状态显示
    function updateTaskStatus(status, message) {
        const $status = $('#taskStatus');
        $status.removeClass('running success error');
        if (status) {
            $status.addClass(status);
        }
        $status.text(message);
    }

    // 显示/隐藏加载效果
    function toggleLoading(show) {
        if (show) {
            $('.loading-container').addClass('active');
        } else {
            $('.loading-container').removeClass('active');
        }
    }

    // 格式化日期时间
    function formatDateTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    // 加载日志数据
    function loadLogs(page) {
        toggleLoading(true);
        
        $.ajax({
            url: `/logs?page=${page}&page_size=${pageSize}`,
            method: 'GET',
            success: function(response) {
                const tbody = $('#logTable tbody');
                tbody.empty();

                response.data.forEach(function(log) {
                    const row = $('<tr>');
                    row.append($('<td>').text(log.id));
                    row.append($('<td>').text(formatDateTime(log.log_time)));
                    row.append($('<td>').text(log.application_id || '-'));
                    const errorCell = $('<td>');
                    const truncatedError = log.error_message.length > 50 ? log.error_message.substring(0, 50) + '...' : log.error_message;
                    errorCell.text(truncatedError);
                    row.append(errorCell);
                    const analysisCell = $('<td>');
                    const truncatedAnalysis = log.analysis_result.length > 40 ? log.analysis_result.substring(0, 30) + '...' : log.analysis_result;
                    analysisCell.text(truncatedAnalysis);
                    row.append(analysisCell);
                    
                    // 添加操作列
                    const actionCell = $('<td>');
                    const detailButton = $('<button>').addClass('view-details-btn').text('详情');
                    detailButton.click(function() {
                        showErrorModal(
                            `错误类型和关键信息：\n${log.error_message}\n\n` +
                            `分析结果：\n${log.analysis_result}\n\n` +
                            `时间：${formatDateTime(log.log_time)}\n` +
                            `ID：${log.id}`
                        );
                    });
                    actionCell.append(detailButton);
                    row.append(actionCell);
                    tbody.append(row);
                });

                // 更新分页信息
                $('#totalRecords').text(response.total);
                $('#totalPages').text(response.total_pages);
                $('#pageInput').val(page);
                totalPages = response.total_pages;
                $('#maxPage').text(response.total_pages);

                // 更新分页按钮状态
                $('#prevPage').prop('disabled', page <= 1);
                $('#nextPage').prop('disabled', page >= response.total_pages);

                currentPage = page;
            },
            error: function() {
                alert('加载日志数据失败');
            },
            complete: function() {
                toggleLoading(false);
            }
        });
    }

    // 触发分析任务
    function triggerAnalysis() {
        if (isTaskRunning) return;

        const $btn = $('#triggerAnalysis');
        $btn.prop('disabled', true);
        isTaskRunning = true;
        updateTaskStatus('running', '正在分析日志...');

        $.ajax({
            url: '/analyze',
            method: 'POST',
            success: function(response) {
                if (response.status === 'success') {
                    updateTaskStatus('success', '分析任务已启动');
                    // 3秒后刷新数据
                    setTimeout(function() {
                        loadLogs(1);
                        updateTaskStatus('', '当前无任务运行');
                    }, 3000);
                } else {
                    updateTaskStatus('error', '分析任务启动失败');
                }
            },
            error: function() {
                updateTaskStatus('error', '分析任务启动失败');
            },
            complete: function() {
                $btn.prop('disabled', false);
                isTaskRunning = false;
            }
        });
    }

    // 绑定事件处理
    $('#triggerAnalysis').click(triggerAnalysis);
    $('#prevPage').click(() => loadLogs(currentPage - 1));
    $('#nextPage').click(() => loadLogs(currentPage + 1));

    // 页码输入处理
    $('#pageInput').on('change', function() {
        const value = parseInt($(this).val());
        if (value && value > 0 && value <= totalPages) {
            loadLogs(value);
        } else {
            $(this).val(currentPage);
        }
    });

    // 每页条数选择处理
    $('#pageSize').on('change', function() {
        pageSize = parseInt($(this).val());
        loadLogs(1);
    });

    // 初始加载
    loadLogs(1);
});
