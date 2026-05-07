document.addEventListener('DOMContentLoaded', () => {
    // --- UI Logic ---
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    const toastEl = document.getElementById('toast');

    function showToast(message, isError = false) {
        toastEl.textContent = message;
        toastEl.style.borderLeft = `4px solid ${isError ? 'var(--danger)' : 'var(--primary)'}`;
        toastEl.classList.add('show');
        setTimeout(() => toastEl.classList.remove('show'), 3000);
    }

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.getAttribute('data-tab');
            
            navItems.forEach(nav => nav.classList.remove('active'));
            tabContents.forEach(tab => tab.classList.remove('active'));
            
            item.classList.add('active');
            document.getElementById(target).classList.add('active');

            if(target === 'scheduled') {
                loadScheduledPosts();
            } else if (target === 'settings') {
                loadConfig();
            }
        });
    });

    // --- API Logic ---
    
    // Load config
    async function loadConfig() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            document.getElementById('fanpageID').value = data.fanpageID || '';
            document.getElementById('token').value = data.token || '';
        } catch (e) {
            console.error("Error loading config:", e);
        }
    }

    // Save config
    document.getElementById('configForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fanpageID = document.getElementById('fanpageID').value;
        const token = document.getElementById('token').value;

        try {
            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fanpageID, token })
            });
            const data = await res.json();
            if(data.status === 'success') {
                showToast(data.message);
            } else {
                showToast(data.message || "Lỗi khi lưu cấu hình!", true);
            }
        } catch (e) {
            showToast("Lỗi mạng khi kết nối tới server!", true);
        }
    });

    // Run Script
    document.getElementById('runScriptBtn').addEventListener('click', async () => {
        const logBox = document.getElementById('systemLog');
        logBox.innerHTML = "Đang bắt đầu tiến trình chạy Auto Post... Vui lòng đợi.\n";
        
        // Switch to dashboard tab to show log
        document.querySelector('[data-tab="dashboard"]').click();
        
        try {
            const res = await fetch('/api/run_script', { method: 'POST' });
            const data = await res.json();
            
            if (data.status === 'success') {
                logBox.innerHTML += `<span style="color: #10b981">${data.output.replace(/\n/g, '<br>')}</span>`;
                showToast("Lên lịch thành công!");
                loadScheduledPosts(); // update count
            } else {
                logBox.innerHTML += `<span style="color: #ef4444">${data.error || data.message}</span>`;
                showToast("Có lỗi xảy ra khi chạy!", true);
            }
        } catch (e) {
            logBox.innerHTML += `<span style="color: #ef4444">Network Error: ${e.message}</span>`;
        }
    });

    // Store posts globally for detail view
    let currentPosts = [];

    // Load Scheduled Posts
    async function loadScheduledPosts() {
        const listEl = document.getElementById('postsList');
        const countEl = document.getElementById('totalPosts');
        
        listEl.innerHTML = '<tr><td colspan="4" class="text-center">Đang tải dữ liệu từ Facebook...</td></tr>';
        
        try {
            const res = await fetch('/api/scheduled_posts');
            const data = await res.json();
            
            if (res.ok && data.status === 'success') {
                currentPosts = data.posts;
                countEl.textContent = currentPosts.length;
                
                if (currentPosts.length === 0) {
                    listEl.innerHTML = '<tr><td colspan="4" class="text-center">Chưa có bài viết nào được lên lịch.</td></tr>';
                    return;
                }
                
                listEl.innerHTML = '';
                currentPosts.forEach(post => {
                    const tr = document.createElement('tr');
                    const msg = post.message || 'Chỉ có ảnh/Không có nội dung';
                    const shortMsg = msg.length > 50 ? msg.substring(0, 50) + '...' : msg;
                    
                    // scheduled_publish_time is unix timestamp in seconds
                    let dateStr = 'N/A';
                    if (post.scheduled_publish_time) {
                        dateStr = new Date(post.scheduled_publish_time * 1000).toLocaleString('vi-VN');
                    } else if (post.created_time) {
                        dateStr = new Date(post.created_time).toLocaleString('vi-VN');
                    }
                    
                    tr.innerHTML = `
                        <td><small>${post.id}</small></td>
                        <td>${shortMsg}</td>
                        <td>${dateStr}</td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="viewPost('${post.id}')" style="margin-right: 5px;">
                                <i class="ph ph-eye"></i> Chi tiết
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="deletePost('${post.id}')">
                                <i class="ph ph-trash"></i> Xoá
                            </button>
                        </td>
                    `;
                    listEl.appendChild(tr);
                });
            } else {
                listEl.innerHTML = `<tr><td colspan="4" class="text-center text-danger">${data.message || 'Lỗi kết nối Facebook. Hãy kiểm tra lại Token.'}</td></tr>`;
                countEl.textContent = 'Lỗi';
            }
        } catch (e) {
            listEl.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Lỗi mạng. Không thể kết nối tới server.</td></tr>';
        }
    }

    document.getElementById('refreshPostsBtn').addEventListener('click', loadScheduledPosts);

    // Global view function
    window.viewPost = function(postId) {
        const post = currentPosts.find(p => p.id === postId);
        if(!post) return;

        document.getElementById('modalId').textContent = post.id;
        
        if (post.scheduled_publish_time) {
            document.getElementById('modalTime').textContent = new Date(post.scheduled_publish_time * 1000).toLocaleString('vi-VN');
        } else {
            document.getElementById('modalTime').textContent = new Date(post.created_time).toLocaleString('vi-VN');
        }

        document.getElementById('modalMessage').textContent = post.message || 'Không có nội dung';

        const imgEl = document.getElementById('modalImage');
        if (post.attachments && post.attachments.data && post.attachments.data.length > 0) {
            const media = post.attachments.data[0].media;
            if (media && media.image) {
                imgEl.src = media.image.src;
                imgEl.style.display = 'block';
            } else {
                imgEl.style.display = 'none';
            }
        } else {
            imgEl.style.display = 'none';
        }

        document.getElementById('modalDeleteBtn').onclick = () => {
            closeModal();
            deletePost(post.id);
        };

        document.getElementById('postModal').classList.add('show');
    };

    // Modal close logic
    function closeModal() {
        document.getElementById('postModal').classList.remove('show');
    }

    document.querySelector('.close-modal').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        if (e.target === document.getElementById('postModal')) {
            closeModal();
        }
    });

    // Global delete function
    window.deletePost = async function(postId) {
        if(!confirm('Bạn có chắc chắn muốn xoá bài viết này khỏi lịch đăng?')) return;
        
        try {
            const res = await fetch(`/api/scheduled_posts/${postId}`, { method: 'DELETE' });
            if (res.ok) {
                showToast("Xoá thành công!");
                loadScheduledPosts();
            } else {
                const data = await res.json();
                showToast(data.message || "Lỗi khi xoá!", true);
            }
        } catch (e) {
            showToast("Lỗi mạng!", true);
        }
    };

    // Initial load
    loadConfig();
    loadScheduledPosts();
});
