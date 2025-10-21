
import csv
import sys

def translate_modbus_command(command):
    """Menerjemahkan perintah Modbus ke dalam format yang mudah dibaca."""
    if command == "010301080001":
        return "Request: Kecepatan spindle"
    elif command == "010600020001":
        return "Perintah: Putar spindle ke kanan"
    elif command == "010600020002":
        return "Perintah: Putar spindle ke kiri"
    elif command == "010600020004":
        return "Perintah: Hentikan spindle"
    elif command.startswith("01060004"):
        try:
            # Kecepatan berada di 2 byte terakhir dari perintah
            speed_hex = command[8:12]
            speed_int = int(speed_hex, 16)
            return f"Perintah: Atur kecepatan spindle ke {speed_int}"
        except (ValueError, IndexError):
            return "Perintah: Atur kecepatan spindle (nilai kecepatan tidak valid)"
    # Response untuk request kecepatan spindle
    elif command.startswith("010302"):
        try:
            speed_hex = command[6:10]
            speed_int = int(speed_hex, 16)
            return f"Response: Kecepatan spindle adalah {speed_int}"
        except (ValueError, IndexError):
            return "Response: Kecepatan spindle (nilai tidak valid)"
    else:
        return "Perintah tidak dikenal"

def group_and_translate_modbus_data(csv_file_path):
    """
    Membaca file CSV berisi data Modbus, mengelompokkan data menjadi perintah,
    dan menerjemahkannya.
    """
    try:
        with open(csv_file_path, 'r', newline='') as infile:
            # Menggunakan DictReader untuk kemudahan akses kolom
            reader = csv.DictReader(infile)
            
            commands = []
            current_command_bytes = []
            last_time = 0.0

            for row in reader:
                try:
                    # Menggunakan .get() untuk menghindari error jika kolom tidak ada
                    start_time_str = row.get('start_time') or row.get('"start_time"')
                    data_str = row.get('data') or row.get('"data"')

                    if start_time_str is None or data_str is None:
                        continue

                    current_time = float(start_time_str)
                    byte = data_str.replace('0x', '').upper().zfill(2)

                    # Jika selisih waktu > 1 detik, anggap sebagai perintah baru
                    if current_command_bytes and (current_time - last_time > 1.0):
                        commands.append("".join(current_command_bytes))
                        current_command_bytes = []

                    current_command_bytes.append(byte)
                    last_time = current_time
                
                except (ValueError, TypeError):
                    # Lewati baris dengan data yang tidak valid
                    continue
            
            # Tambahkan perintah terakhir yang tersisa
            if current_command_bytes:
                commands.append("".join(current_command_bytes))

            # Terjemahkan dan cetak setiap perintah
            print(f"Hasil Analisa dari file: {csv_file_path}\n")
            for cmd_with_crc in commands:
                # Perintah Modbus biasanya memiliki 2 byte CRC di akhir
                if len(cmd_with_crc) > 4:
                    cmd_without_crc = cmd_with_crc[:-4]
                    crc = cmd_with_crc[-4:]
                    translation = translate_modbus_command(cmd_without_crc)
                    print(f"Perintah: {cmd_without_crc} (CRC: {crc}) -> {translation}")
                else:
                    # Jika perintah terlalu pendek untuk memiliki CRC
                    translation = translate_modbus_command(cmd_with_crc)
                    print(f"Perintah: {cmd_with_crc} -> {translation}")

    except FileNotFoundError:
        print(f"Error: File tidak ditemukan di {csv_file_path}")
    except Exception as e:
        print(f"Terjadi error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # Gunakan path default jika tidak ada argumen yang diberikan
        csv_path = "data-modbus-lincnc2.csv"
    
    group_and_translate_modbus_data(csv_path)
