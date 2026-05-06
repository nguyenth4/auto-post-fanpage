bước 1: cài python 3.6, nhớ tích vào ô add python 3.6 to path trước khi ấn install now (nếu máy ko có python thì không cần quan tâm, nếu có bản cũ thì nếu được gỡ bản cũ là hay nhất, nếu không thì phải vào C:\users\tên user name\AppData\Local\Programs\Python\Scripts, rồi mở CMD tại folder đó rồi cài pip - sẽ nói ở bước 5)


trong lúc làm bước 1 ta tranh thủ.

bước 2: vào trang http://findmyfbid.com/ để lấy ID fanpage bằng cách pate địa chỉ fanpage ca mình vào. sau khi lấy được ID thì pate vào python

bước 3: vào trang https://developers.facebook.com/tools/explorer/
ấn vào ô " nhận mã" bên phải, chọn "nhận mã truy cập trang", chọn fanpage mình cần auto.

bước 4: ấn vào ô nhận mã lúc đầu mà bây giờ đã đổi thành tên fanpage. chọn "yêu cầu publish_pages"

bước 5: mình ấn phím window+R hoặc mở CMD từ start menu: sau đó gõ lệnh sau để cài thư viện cho python:
pip install requests pyexcel pyexcel-xls pyexcel-xlsx

bước 6: copy nội dung dài dài trong phần Mã truy cập vào phần token trong python.

bước 7: mở file excel content.xlsx sửa ngày tháng sao cho hợp lý. Facebook quy định bài viết hẹn giờ phải ít nhất 6 phút sau thời điểm hiện tại và không quá 6 tháng. nên chạy thử (VD: hẹn giờ vào 12 tiếng sau )

bước 8: mở file python để chạy lần lượt pate ID fanpage và token

bước 9: nếu thành công sẽ hiện ra chữ post successful, nếu lỗi nhớ chụp lại để check lỗi.