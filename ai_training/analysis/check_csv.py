import csv

# Đổi lại đường dẫn file nếu cần
file_path = 'dataset/samples.csv' 

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    expected_cols = len(header)
    
    print(f"Số cột chuẩn từ header: {expected_cols}\n{'-'*40}")
    
    error_count = 0
    for i, row in enumerate(reader, start=2): # Dòng 1 là header
        if len(row) > expected_cols:
            error_count += 1
            print(f"⚠️ Lỗi ở DÒNG {i}: Đang có {len(row)} cột (dư {len(row) - expected_cols} cột)")
            print(f"Nội dung dòng bị lỗi: {row}\n")
            
    if error_count == 0:
        print("Tuyệt vời! Không có dòng nào bị dư cột.")