import pyexcel as pe
from datetime import datetime, timedelta

# Cấu trúc file Excel
data = [["Message", "Year", "Month", "Day", "Hour", "Minute", "Second"]]

# Danh sách mẫu nội dung theo khung giờ (Xoay vòng cho 7 ngày)
morning_content = [
    "Chào buổi sáng cộng đồng In 3D! Bạn đã sẵn sàng cho bản in đầu tiên trong ngày chưa?",
    "Kiến thức: Nhựa PLA là gì và tại sao nó lại phổ biến nhất cho người mới bắt đầu?",
    "Tư duy thiết kế: Tại sao chúng ta nên ưu tiên thiết kế không cần support?",
    "Chào ngày mới! Một tách cafe và tiếng máy in 3D chạy rào rào là khởi đầu hoàn hảo.",
    "Bạn có biết: Máy in 3D đầu tiên được ra đời từ năm 1984 bởi Chuck Hull?",
    "Mẹo nhỏ: Luôn kiểm tra bàn in (Leveling) trước khi bắt đầu bản in dài.",
    "Hôm nay bạn định in gì? Hãy chia sẻ ý tưởng dưới comment nhé!"
]

noon_content = [
    "Giờ nghỉ trưa cùng ngắm nhìn mẫu in con rồng khớp nối cực kỳ linh hoạt này nhé!",
    "Ứng dụng: In 3D trong y học đang cứu sống hàng ngàn người mỗi năm.",
    "Mẫu in thực tế: Chiếc giá đỡ điện thoại tự thiết kế và in chỉ trong 2 tiếng.",
    "Bạn thích nhựa màu Solid hay màu Silk (bóng) hơn? Hãy cùng bình chọn nào.",
    "Review nhanh: Nhựa PETG - Sự kết hợp hoàn hảo giữa độ bền của ABS và dễ in của PLA.",
    "Sản phẩm hôm nay: Vỏ case máy tính in 3D cực độc lạ.",
    "Cùng xem độ chi tiết của bản in 0.1mm trên máy in Resin."
]

evening_content = [
    "Lỗi thường gặp: Tại sao bản in bị bong góc (Warping) và cách khắc phục triệt để.",
    "Thủ thuật: Cách tối ưu hóa Infill để vừa tiết kiệm nhựa vừa đảm bảo độ chắc chắn.",
    "Hỏi đáp: Bạn đang dùng phần mềm cắt lớp (Slicer) nào? Cura, Orca hay PrusaSlicer?",
    "Review máy: Sự khác biệt giữa máy in FDM truyền thống và máy in Resin độ phân giải cao.",
    "Cách xử lý hậu kỳ bản in: Từ chà nhám đến sơn màu sao cho chuyên nghiệp.",
    "Chia sẻ: Những trang web tải mẫu 3D miễn phí tốt nhất hiện nay (Thingiverse, Printables...)",
    "Thảo luận: In 3D có thực sự thay đổi được ngành sản xuất truyền thống?"
]

night_content = [
    "Máy in đang chạy xuyên đêm... Sáng mai thức dậy sẽ có một món quà bất ngờ.",
    "Góc thư giãn: Ngắm nhìn mô hình thành phố in 3D có gắn đèn LED cực chill.",
    "Dành cho cú đêm: Những mẫu in 'bất khả thi' nếu không có máy in 3D.",
    "Lưu ý an toàn: Những điều cần kiểm tra trước khi để máy in chạy tự động ban đêm.",
    "Nghệ thuật in 3D: Khi kỹ thuật hòa quyện cùng sự sáng tạo không giới hạn.",
    "Tầm nhìn: In 3D nhà ở - Tương lai của ngành xây dựng đang đến rất gần.",
    "Chúc cả nhà ngủ ngon và có những bản in thành công vào sáng mai!"
]

# Tạo dữ liệu cho 7 ngày tới
start_date = datetime(2026, 5, 7) # Bắt đầu từ ngày mai

for i in range(7):
    current_day = start_date + timedelta(days=i)
    year, month, day = current_day.year, current_day.month, current_day.day
    
    # Thêm 4 bài đăng mỗi ngày theo khung giờ yêu cầu
    data.append([morning_content[i], year, month, day, 7, 30, 0])  # 7h30 sáng
    data.append([noon_content[i], year, month, day, 12, 0, 0])    # 12h00 trưa
    data.append([evening_content[i], year, month, day, 20, 30, 0]) # 20h30 tối
    data.append([night_content[i], year, month, day, 23, 0, 0])    # 23h00 đêm

# Lưu thành file content.xlsx
pe.save_as(array=data, dest_file_name="content.xlsx")

print(f"Đã tạo thành công 28 bài đăng tự động cho 7 ngày tới vào file content.xlsx!")
