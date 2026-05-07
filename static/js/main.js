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
            } else if (target === 'connections') {
                loadConnections();
            }
        });
    });

    // --- API Logic ---

    function providerLabel(p) {
        if (p === 'facebook_page') return 'Facebook Page';
        if (p === 'tiktok') return 'TikTok';
        if (p === 'youtube') return 'YouTube';
        if (p === 'google') return 'Google';
        return p;
    }

    function statusBadge(status) {
        const color = status === 'connected' ? '#10b981' : (status === 'expired' ? '#f59e0b' : '#ef4444');
        return `<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.12);color:${color};font-weight:600;font-size:12px;">${status}</span>`;
    }

    async function loadConnections() {
        const listEl = document.getElementById('connectionsList');
        if (!listEl) return;
        listEl.innerHTML = '<tr><td colspan="5" class="text-center">Đang tải...</td></tr>';
        try {
            const res = await fetch('/api/connections');
            const data = await res.json();
            if (!res.ok || data.status !== 'success') {
                listEl.innerHTML = `<tr><td colspan="5" class="text-center text-danger">${data.message || 'Không tải được kết nối.'}</td></tr>`;
                return;
            }
            const accounts = data.accounts || [];
            if (accounts.length === 0) {
                listEl.innerHTML = '<tr><td colspan="5" class="text-center">Chưa có kết nối nào.</td></tr>';
                loadFacebookPages();
                return;
            }
            listEl.innerHTML = '';
            accounts.forEach(acc => {
                const tr = document.createElement('tr');
                const updated = acc.updated_at ? new Date(acc.updated_at).toLocaleString('vi-VN') : '—';
                const name = acc.display_name || acc.external_id;
                const err = acc.last_error ? `<div class="text-muted" style="max-width:420px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${acc.last_error}</div>` : '';
                tr.innerHTML = `
                    <td>${providerLabel(acc.provider)}</td>
                    <td>
                        <div style="font-weight:600;">${name}</div>
                        <div class="text-muted"><small>${acc.external_id}</small></div>
                        ${err}
                    </td>
                    <td>${statusBadge(acc.status)}</td>
                    <td><small>${updated}</small></td>
                    <td>
                        <button class="btn btn-danger btn-sm" onclick="disconnectAccount(${acc.id})">
                            <i class="ph ph-trash"></i> Ngắt
                        </button>
                    </td>
                `;
                listEl.appendChild(tr);
            });
            loadFacebookPages();
        } catch (e) {
            listEl.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Lỗi mạng khi tải kết nối.</td></tr>';
        }
    }

    async function loadFacebookPages() {
        const selectEl = document.getElementById('fbPageSelect');
        if (!selectEl) return;
        const badgeEl = document.getElementById('fbPageStatus');
        try {
            const res = await fetch('/api/facebook/pages');
            const data = await res.json();
            if (!res.ok || data.status !== 'success') return;

            const pages = data.pages || [];
            const active = data.active_page_id || '';
            const prev = selectEl.value;
            selectEl.innerHTML = '<option value="">— Chọn Facebook Page —</option>';
            pages.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.external_id;
                opt.textContent = p.display_name || p.external_id;
                opt.dataset.status = p.status || '';
                selectEl.appendChild(opt);
            });
            selectEl.value = active || prev || '';

            if (badgeEl) {
                const selectedOpt = selectEl.options[selectEl.selectedIndex];
                const st = (selectedOpt && selectedOpt.dataset && selectedOpt.dataset.status) ? selectedOpt.dataset.status : '';
                updateFbBadge(badgeEl, st);
            }
        } catch (_) {}
    }

    function updateFbBadge(el, status) {
        el.className = 'badge';
        if (!status) {
            el.classList.add('badge-muted');
            el.textContent = 'Chưa chọn';
            return;
        }
        if (status === 'connected') {
            el.classList.add('badge-success');
            el.textContent = 'Connected';
        } else if (status === 'expired') {
            el.classList.add('badge-warn');
            el.textContent = 'Expired';
        } else if (status === 'error') {
            el.classList.add('badge-danger');
            el.textContent = 'Error';
        } else {
            el.classList.add('badge-muted');
            el.textContent = status;
        }
    }

    async function setActiveFacebookPage(pageId) {
        try {
            const res = await fetch('/api/facebook/active', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ page_id: pageId })
            });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                showToast('Đã chọn Page.');
                loadScheduledPosts();
            } else {
                showToast(data.message || 'Không chọn được Page.', true);
            }
        } catch (_) {
            showToast('Lỗi mạng!', true);
        }
    }

    window.disconnectAccount = async function(accountId) {
        if (!confirm('Bạn có chắc chắn muốn ngắt kết nối này?')) return;
        try {
            const res = await fetch(`/api/connections/${accountId}/disconnect`, { method: 'POST' });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                showToast('Đã ngắt kết nối.');
                loadConnections();
            } else {
                showToast(data.message || 'Không ngắt được kết nối.', true);
            }
        } catch (e) {
            showToast('Lỗi mạng!', true);
        }
    };

    const refreshConnectionsBtn = document.getElementById('refreshConnectionsBtn');
    if (refreshConnectionsBtn) {
        refreshConnectionsBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/connections/refresh', { method: 'POST' });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    showToast(`Đã refresh: ${data.refreshed}`);
                    loadConnections();
                } else {
                    showToast(data.message || 'Refresh thất bại.', true);
                }
            } catch (e) {
                showToast('Lỗi mạng!', true);
            }
        });
    }

    const fbManualForm = document.getElementById('fbManualForm');
    if (fbManualForm) {
        fbManualForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fanpageID = document.getElementById('fbFanpageID').value.trim();
            const token = document.getElementById('fbToken').value.trim();
            if (!fanpageID || !token) {
                showToast('Vui lòng nhập đủ Fanpage ID và token.', true);
                return;
            }
            try {
                const res = await fetch('/api/connect/facebook/manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fanpageID, token })
                });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    showToast(data.message || 'Đã lưu kết nối Facebook.');
                    document.getElementById('fbToken').value = '';
                    loadConnections();
                    loadScheduledPosts();
                } else {
                    showToast(data.message || 'Không lưu được kết nối.', true);
                }
            } catch (err) {
                showToast('Lỗi mạng khi lưu kết nối.', true);
            }
        });
    }

    const ttManualForm = document.getElementById('ttManualForm');
    if (ttManualForm) {
        ttManualForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const open_id = document.getElementById('ttOpenId').value.trim();
            const token = document.getElementById('ttToken').value.trim();
            if (!open_id || !token) {
                showToast('Vui lòng nhập đủ Open ID và token.', true);
                return;
            }
            try {
                const res = await fetch('/api/connect/tiktok/manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ open_id, token })
                });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    showToast(data.message || 'Đã lưu kết nối TikTok.');
                    document.getElementById('ttToken').value = '';
                    loadConnections();
                } else {
                    showToast(data.message || 'Không lưu được kết nối TikTok.', true);
                }
            } catch (err) {
                showToast('Lỗi mạng khi lưu kết nối TikTok.', true);
            }
        });
    }

    const ytManualForm = document.getElementById('ytManualForm');
    if (ytManualForm) {
        ytManualForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const channel_id = document.getElementById('ytChannelId').value.trim();
            const token = document.getElementById('ytToken').value.trim();
            if (!channel_id || !token) {
                showToast('Vui lòng nhập đủ Channel ID và token.', true);
                return;
            }
            try {
                const res = await fetch('/api/connect/youtube/manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ channel_id, token })
                });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    showToast(data.message || 'Đã lưu kết nối YouTube.');
                    document.getElementById('ytToken').value = '';
                    loadConnections();
                } else {
                    showToast(data.message || 'Không lưu được kết nối YouTube.', true);
                }
            } catch (err) {
                showToast('Lỗi mạng khi lưu kết nối YouTube.', true);
            }
        });
    }

    const quickPostTikTok = document.getElementById('quickPostTikTok');
    if (quickPostTikTok) {
        quickPostTikTok.addEventListener('submit', async (e) => {
            e.preventDefault();
            const account_id = document.getElementById('ttPostAccount').value.trim();
            const video_url = document.getElementById('ttVideoUrl').value.trim();
            const caption = document.getElementById('ttCaption').value.trim();
            if (!account_id || !video_url) {
                showToast('Cần Open ID + video_url.', true);
                return;
            }
            try {
                const res = await fetch('/api/post/tiktok', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ account_id, video_url, caption })
                });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    showToast('Đã gửi request đăng TikTok.');
                } else {
                    showToast(data.message || 'Post TikTok thất bại.', true);
                }
            } catch (err) {
                showToast('Lỗi mạng khi post TikTok.', true);
            }
        });
    }

    const quickPostYouTube = document.getElementById('quickPostYouTube');
    if (quickPostYouTube) {
        quickPostYouTube.addEventListener('submit', async (e) => {
            e.preventDefault();
            const channel_id = document.getElementById('ytPostChannel').value.trim();
            const title = document.getElementById('ytTitle').value.trim();
            const description = document.getElementById('ytDesc').value.trim();
            const privacy_status = document.getElementById('ytPrivacy').value;
            const fileEl = document.getElementById('ytVideoFile');
            const file = fileEl && fileEl.files ? fileEl.files[0] : null;

            if (!channel_id || !file) {
                showToast('Cần Channel ID + file video.', true);
                return;
            }

            const fd = new FormData();
            fd.append('channel_id', channel_id);
            fd.append('title', title);
            fd.append('description', description);
            fd.append('privacy_status', privacy_status);
            fd.append('video', file);

            showToast('Đang upload YouTube... (có thể mất vài phút)');
            try {
                const res = await fetch('/api/post/youtube', { method: 'POST', body: fd });
                const data = await res.json();
                if (res.ok && data.status === 'success') {
                    showToast('Upload YouTube thành công!');
                } else {
                    showToast(data.message || 'Upload YouTube thất bại.', true);
                }
            } catch (err) {
                showToast('Lỗi mạng khi upload YouTube.', true);
            }
        });
    }

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
                const msg = data.message || 'Không lấy được dữ liệu.';
                listEl.innerHTML = `<tr><td colspan="4" class="text-center text-danger">${msg}</td></tr>`;

                // Better UX for the "Total scheduled posts" widget
                if ((msg || '').toLowerCase().includes('chưa kết nối')) {
                    countEl.textContent = 'Chưa kết nối';
                    showToast('Bạn chưa kết nối Facebook Page. Vào tab “Kết nối” để connect.', true);
                } else if ((msg || '').toLowerCase().includes('hết hạn')) {
                    countEl.textContent = 'Hết hạn';
                    showToast('Token Facebook có thể đã hết hạn. Vào tab “Kết nối” để reconnect.', true);
                } else {
                    countEl.textContent = 'Không khả dụng';
                }
            }
        } catch (e) {
            listEl.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Lỗi mạng. Không thể kết nối tới server.</td></tr>';
            countEl.textContent = 'Mất mạng';
        }
    }

    document.getElementById('refreshPostsBtn').addEventListener('click', loadScheduledPosts);

    const fbPageSelect = document.getElementById('fbPageSelect');
    if (fbPageSelect) {
        fbPageSelect.addEventListener('change', () => {
            const v = fbPageSelect.value;
            if (!v) return;
            const badgeEl = document.getElementById('fbPageStatus');
            if (badgeEl) {
                const selectedOpt = fbPageSelect.options[fbPageSelect.selectedIndex];
                updateFbBadge(badgeEl, selectedOpt && selectedOpt.dataset ? selectedOpt.dataset.status : '');
            }
            setActiveFacebookPage(v);
        });
    }

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
    loadConnections();
    loadScheduledPosts();
});
