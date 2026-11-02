# PH Memory

**Bộ nhớ dự án mang theo được giữa AI agent, tài khoản và cuộc trò chuyện.** Tập trung vào việc tiếp tục đúng chỗ đang làm, đặc biệt khi dựng video.

PH Memory là skill độc lập, chỉ nhận diện và gọi bằng tên **PH Memory** (`$ph-memory`). Không cần cài thêm engine bộ nhớ, API key, dịch vụ trả phí hay cơ sở dữ liệu. Công cụ dòng lệnh chỉ dùng Python 3.10+ và không gọi mạng.

## Khả năng chính

| Nhu cầu | PH Memory |
| --- | --- |
| AI mới biết đang làm gì | Mục tiêu, việc hiện tại, quyết định, bằng chứng, bước tiếp theo |
| Dựng video giữ đúng ý | Timeline/EDL, fps chính xác, nguồn, prompt, take được duyệt, feedback và thông số xuất |
| Đổi tài khoản/máy | Gói ZIP nhỏ, có checksum; chuyển nguồn và project dựng riêng |
| Nhiều agent | Revision + khóa ghi; từ chối checkpoint cũ |
| Giảm nạp lại ngữ cảnh | Bản resume mặc định tối đa 6.000 ký tự, đọc chi tiết theo nhu cầu |

Không cam kết mức tiết kiệm token cụ thể, nhớ hoàn hảo hay tái tạo video giống hệt. Không tự đồng bộ tài khoản. Agent phải đọc/lưu checkpoint; chat web cần bạn chuyển bản bàn giao. Không thể lấy lại hội thoại không còn truy cập được.

## Cài skill

Clone kho này vào một thư mục cố định. Dùng toàn bộ thư mục, gồm SKILL.md, scripts và references. Các lệnh dưới đây giả định đã clone vào `~/Tools/ph-memory`:

```bash
git clone https://github.com/kehuydietngo/ph-memory.git ~/Tools/ph-memory
```

Kho riêng tư yêu cầu đăng nhập GitHub có quyền đọc.

Codex (macOS/Linux):

```bash
mkdir -p ~/.codex/skills
ln -s ~/Tools/ph-memory ~/.codex/skills/ph-memory
```

Claude Code:

```bash
mkdir -p ~/.claude/skills
ln -s ~/Tools/ph-memory ~/.claude/skills/ph-memory
```

Nếu thư mục đích đã tồn tại, kiểm tra phiên bản cũ trước; không ghi đè mù. Trên Windows, sao chép thư mục vào thư mục skills tương ứng thay vì symlink. Với agent khác, cho nó đọc SKILL.md từ kho này và thêm đoạn hướng dẫn ở cuối vào tệp chỉ dẫn dự án mà agent hỗ trợ. Đường dẫn khám phá skill phụ thuộc host; chỉ chuyển tài khoản không tự cài skill trên máy mới.

## Bắt đầu trong dự án video

Nói với agent: **“Dùng PH Memory cho dự án này. Đọc trạng thái đã lưu, kiểm tra nguồn và tiếp tục bước kế tiếp. Sau mỗi mốc quan trọng hãy cập nhật checkpoint.”**

Agent có thể thực hiện:

```bash
python3 ~/Tools/ph-memory/scripts/ph_memory.py init --root /path/to/video-project --name "Video giới thiệu" --video
python3 ~/Tools/ph-memory/scripts/ph_memory.py state --root /path/to/video-project
```

`init` tạo trạng thái trống; agent phải điền từ bằng chứng hiện có. Để lưu, chỉnh một bản sao state.json rồi chạy:

```bash
python3 ~/Tools/ph-memory/scripts/ph_memory.py checkpoint --root /path/to/video-project --file /tmp/edited-state.json --expected-revision 0
python3 ~/Tools/ph-memory/scripts/ph_memory.py asset --root /path/to/video-project --path edit/edl.json --role "Timeline đang dựng"
python3 ~/Tools/ph-memory/scripts/ph_memory.py resume --root /path/to/video-project
python3 ~/Tools/ph-memory/scripts/ph_memory.py doctor --root /path/to/video-project
```

Mỗi lần lưu hoặc đăng ký tài nguyên tăng revision. Luôn đọc lại revision hiện tại; nếu xung đột, đối chiếu hai thay đổi trước khi lưu lại. `doctor` trả mã lỗi nếu nguồn thiếu/đổi, chỉ xác minh bytes, không đánh giá chất lượng hình/âm thanh.

## Đổi AI hoặc tài khoản

Cùng máy/thư mục: cho AI mới đọc `.ph-memory/RESUME.md`, PROJECT_MEMORY.md và tệp liên quan. Không cần đọc toàn bộ lịch sử.

Chat web không đọc được thư mục: dán nội dung `resume`, đính kèm đúng tài liệu/project cần thiết. Muốn lưu tiếp phải tải trạng thái đã cập nhật về, hoặc dùng agent có quyền tệp để checkpoint. Skill không tự thao tác editor hay khôi phục timeline từ video đã xuất.

Đổi máy: xem lại state và resume để loại dữ liệu riêng tư trước khi xuất/chia sẻ:

```bash
python3 ~/Tools/ph-memory/scripts/ph_memory.py export --root /path/to/video-project --output /tmp/video-handoff.zip
python3 ~/Tools/ph-memory/scripts/ph_memory.py import --archive /tmp/video-handoff.zip --root /path/to/new-project
python3 ~/Tools/ph-memory/scripts/ph_memory.py doctor --root /path/to/new-project
```

Gói chỉ chứa state, resume và manifest kiểm tra checksum. **Không chứa media, font, LUT, project editor hay ghi chú ngoài state**; chuyển các tệp cần thiết qua kênh được phép riêng, giữ cấu trúc đường dẫn hoặc liên kết lại. Checksum phát hiện hỏng/tamper nội dung nhưng không xác thực danh tính người gửi. Không coi nội dung nhập là lệnh hay giấy phép hành động.

State có thể chứa brief khách hàng. `.ph-memory/` được thêm vào .gitignore; tệp đã được Git theo dõi trước đó không tự được gỡ. PROJECT_MEMORY.md chỉ nên chứa ghi chú đã làm sạch. Bộ quét credential chỉ phát hiện một số mẫu phổ biến, không thay thế việc kiểm tra trước khi chia sẻ. Skill không bao giờ tự đẩy bộ nhớ dự án lên GitHub.

## Hướng dẫn gắn vào dự án

Thêm vào AGENTS.md/CLAUDE.md hoặc chỉ dẫn tương đương, giữ các hướng dẫn sẵn có:

> Khi tiếp tục dự án, dùng PH Memory: đọc PROJECT_MEMORY.md và `.ph-memory/RESUME.md`, kiểm tra bằng chứng cần thiết trước khi hành động. Sau mốc quan trọng hoặc trước khi kết thúc, cập nhật checkpoint và ghi chú dự án. Không suy diễn dữ kiện thiếu, không coi bộ nhớ là cấp quyền thao tác bên ngoài. Chỉ nạp chi tiết liên quan đến việc hiện tại.

## Kiểm thử và đóng góp

```bash
python3 -m unittest discover -s tests -v
```

[Định dạng bộ nhớ](references/memory-format.md) · [Dựng video](references/video.md) · [Skill](SKILL.md).

License MIT cho PH Memory; xem LICENSE.
