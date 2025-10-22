import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import struct

# --- Konstanta Modbus berdasarkan manual ---
SLAVE_ID = 1
RPM_CONTROL_ADDR = 0x0089
SPEED_MONITOR_ADDR = 0x0000
FORCE_ENABLE_ADDR = 0x0062
# FORCE_DISABLE_ADDR = 0x0063
RPM_STEP = 100

# --- Variabel Global ---
ser = None
is_connected = False
monitoring_thread = None
stop_monitoring = False

# --- Fungsi Logika Modbus Manual ---

def calculate_crc(data):
    """Menghitung CRC16 untuk data Modbus."""
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)

def send_modbus_request(slave_id, function_code, address, value=None, count=None, custom_data=None):
    """Membangun, mengirim, dan memvalidasi frame Modbus RTU."""
    if not is_connected or not ser:
        raise serial.SerialException("Port serial tidak terhubung.")

    # Membangun PDU (Protocol Data Unit)
    if function_code == 0x03 or function_code == 0x04:  # Read Holding/Input Registers
        pdu = struct.pack('>HH', address, count)
    elif function_code == 0x06:  # Write Single Register
        pdu = struct.pack('>HH', address, value)
    elif function_code == 0x42 and custom_data is not None: # Custom function code
        pdu = custom_data
    else:
        raise ValueError("Function code tidak didukung.")

    # Membangun ADU (Application Data Unit)
    adu = struct.pack('B', slave_id) + struct.pack('B', function_code) + pdu
    adu += calculate_crc(adu)

    # Mengirim dan menerima data
    print(f"Sending Modbus Frame: {adu.hex().upper()}") # Print message for debugging
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(adu)
    
    # Waktu tunggu untuk respons, bisa disesuaikan
    time.sleep(0.1) 
    
    response = ser.read(ser.in_waiting)

    if not response:
        raise ModbusException("Tidak ada respons dari driver.")

    # Validasi Respons
    response_crc = response[-2:]
    response_data = response[:-2]
    if calculate_crc(response_data) != response_crc:
        raise ModbusException("CRC respons tidak valid.")

    response_slave_id = response[0]
    response_fc = response[1]

    if response_slave_id != slave_id:
        raise ModbusException("Slave ID respons tidak cocok.")

    # Cek error exception dari Modbus
    if response_fc & 0x80:
        error_code = response[2]
        raise ModbusException(f"Driver merespons dengan error code: {error_code}")
    
    if response_fc != function_code:
        raise ModbusException("Function code respons tidak cocok.")

    return response[2:-2] # Kembalikan data payload

class ModbusException(Exception):
    """Custom exception untuk error Modbus."""
    pass

# --- Fungsi Logika Backend ---

def find_com_ports():
    """Mencari semua COM port yang tersedia."""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def connect_modbus():
    """Menghubungkan ke port serial."""
    global ser, is_connected, stop_monitoring, monitoring_thread
    
    if is_connected:
        messagebox.showinfo("Info", "Sudah terhubung.")
        return

    port = com_port_var.get()
    baudrate = int(baud_var.get())
    parity = parity_map[parity_var.get()]
    stopbits = int(stop_bits_var.get())
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            timeout=1
        )
        
        if not ser.is_open:
            raise serial.SerialException("Gagal membuka port serial.")
            
        is_connected = True
        status_conn_label.config(text=f"Status: Terhubung ke {port}", foreground="green")
        toggle_controls(True)
        
        stop_monitoring = False
        monitoring_thread = threading.Thread(target=monitor_speed, daemon=True)
        monitoring_thread.start()
        
    except Exception as e:
        messagebox.showerror("Koneksi Gagal", f"Tidak dapat terhubung:\n{e}")
        status_conn_label.config(text="Status: Gagal terhubung", foreground="red")

def disconnect_modbus():
    """Memutuskan koneksi serial."""
    global ser, is_connected, stop_monitoring
    
    if not is_connected:
        return

    try:
        stop_spindle(show_status=False) 
    except Exception:
        pass

    stop_monitoring = True
    if monitoring_thread:
        monitoring_thread.join(timeout=1.5)
        
    if ser and ser.is_open:
        ser.close()
        
    is_connected = False
    status_conn_label.config(text="Status: Terputus", foreground="red")
    actual_rpm_label.config(text="RPM Aktual: 0")
    toggle_controls(False)

def toggle_controls(enable):
    """Enable atau disable widget kontrol."""
    state = "normal" if enable else "disabled"
    for widget in control_widgets:
        widget.config(state=state)
    
    connect_button.config(state="disabled" if enable else "normal")
    disconnect_button.config(state="normal" if enable else "disabled")
    for widget in connection_widgets:
        widget.config(state="disabled" if enable else "normal")

def update_gui_from_thread(label, text):
    """Helper untuk update GUI dari thread lain."""
    try:
        label.config(text=text)
    except tk.TclError:
        pass

def monitor_speed():
    """Thread untuk memonitor kecepatan motor."""
    global stop_monitoring
    while not stop_monitoring:
        try:
            if not is_connected:
                break
                
            # Baca register kecepatan (Function Code 0x04)
            data = send_modbus_request(
                slave_id=SLAVE_ID,
                function_code=0x04, 
                address=SPEED_MONITOR_ADDR,
                count=1
            )
            
            # Response: [Byte Count, Value High, Value Low]
            if len(data) >= 3 and data[0] == 2:
                speed = struct.unpack('>h', data[1:3])[0] # signed 16-bit
                root.after(0, update_gui_from_thread, actual_rpm_label, f"RPM Aktual: {speed}")
            else:
                root.after(0, update_gui_from_thread, actual_rpm_label, "RPM Aktual: Error Baca")
                
        except Exception:
            if is_connected:
                root.after(0, disconnect_modbus)
            break
            
        time.sleep(1)

def _send_custom_command(data):
    """Mengirim perintah Modbus non-standar."""
    if not is_connected:
        return
    try:
        send_modbus_request(
            slave_id=SLAVE_ID,
            function_code=0x06,
            address=FORCE_ENABLE_ADDR,
            custom_data=data
        )
    except Exception as e:
        status_main_label.config(text=f"Error Perintah: {e}", foreground="red")
        
def enable_drive():
    """Mengirim perintah Enable Drive (Servo ON)."""
    _send_custom_command(1)
    status_main_label.config(text="Status: Drive Enabled", foreground="blue")

def disable_drive():
    """Mengirim perintah Disable Drive (Servo OFF)."""
    _send_custom_command(0)
    status_main_label.config(text="Status: Drive Disabled", foreground="gray")

def adjust_rpm(delta):
    """Menambah atau mengurangi nilai RPM di entry box."""
    try:
        current_val = int(rpm_var.get())
        new_val = current_val + delta
        rpm_var.set(str(new_val))
    except ValueError:
        rpm_var.set("0")

def send_rpm_command():
    """Mengirim RPM ke driver."""
    if not is_connected:
        messagebox.showwarning("Peringatan", "Harap hubungkan ke driver terlebih dahulu.")
        return
        
    try:
        rpm = int(rpm_var.get())
        
        enable_drive()
        
        # Kirim perintah RPM (Function Code 0x06)
        send_modbus_request(
            slave_id=SLAVE_ID,
            function_code=0x06,
            address=RPM_CONTROL_ADDR,
            value=rpm
        )
        
        status_main_label.config(text=f"Status: Perintah RPM {rpm} terkirim", foreground="blue")
        
    except Exception as e:
        status_main_label.config(text=f"Error Kirim RPM: {e}", foreground="red")

def set_direction(direction):
    """Tombol shortcut untuk set arah lalu kirim."""
    try:
        rpm = abs(int(rpm_var.get()))
        if rpm == 0:
            rpm = 1000
            
        if direction == 'cw':
            rpm_var.set(str(-rpm))
        else:
            rpm_var.set(str(rpm))
            
        send_rpm_command()
        
    except ValueError:
        rpm_var.set("1000")
        send_rpm_command()

def stop_spindle(show_status=True):
    """Mengirim perintah berhenti dan disable drive."""
    if not is_connected:
        return
        
    try:
        # Kirim 0 RPM
        send_modbus_request(
            slave_id=SLAVE_ID,
            function_code=0x06,
            address=RPM_CONTROL_ADDR,
            value=0
        )
        
        disable_drive()
        
        rpm_var.set("0")
        if show_status:
            status_main_label.config(text="Status: Spindle Berhenti", foreground="gray")
            
    except Exception as e:
        if show_status:
            status_main_label.config(text=f"Error Stop: {e}", foreground="red")

def on_closing():
    """Handler saat jendela ditutup."""
    disconnect_modbus()
    root.destroy()

# --- Setup GUI ---
root = tk.Tk()
root.title("Kontrol Spindle Modbus T3a/T3L (Manual)")
root.geometry("400x320")

# --- Variabel GUI ---
com_port_var = tk.StringVar()
baud_var = tk.StringVar(value="38400")
parity_var = tk.StringVar(value="Even")
stop_bits_var = tk.StringVar(value="1")
rpm_var = tk.StringVar(value="1000")

parity_map = {
    "None": "N",
    "Even": "E",
    "Odd": "O"
}

# --- Frame Koneksi ---
conn_frame = ttk.LabelFrame(root, text="Koneksi Serial")
conn_frame.pack(fill="x", padx=10, pady=5)

conn_grid = ttk.Frame(conn_frame)
conn_grid.pack(padx=5, pady=5)

ttk.Label(conn_grid, text="Port:").grid(row=0, column=0, padx=5, sticky="w")
com_port_combo = ttk.Combobox(conn_grid, textvariable=com_port_var, width=10)
com_port_combo['values'] = find_com_ports()
if com_port_combo['values']:
    com_port_var.set(com_port_combo['values'][0])
com_port_combo.grid(row=0, column=1, padx=5)

ttk.Label(conn_grid, text="Baud:").grid(row=0, column=2, padx=5, sticky="w")
baud_combo = ttk.Combobox(conn_grid, textvariable=baud_var, width=8, values=["9600", "19200", "38400", "57600", "115200"])
baud_combo.grid(row=0, column=3, padx=5)

ttk.Label(conn_grid, text="Parity:").grid(row=1, column=0, padx=5, sticky="w")
parity_combo = ttk.Combobox(conn_grid, textvariable=parity_var, width=10, values=["None", "Even", "Odd"])
parity_combo.grid(row=1, column=1, padx=5)

ttk.Label(conn_grid, text="Stop Bits:").grid(row=1, column=2, padx=5, sticky="w")
stop_bits_combo = ttk.Combobox(conn_grid, textvariable=stop_bits_var, width=8, values=["1", "2"])
stop_bits_combo.grid(row=1, column=3, padx=5)

connect_button = ttk.Button(conn_frame, text="Connect", command=connect_modbus)
connect_button.pack(side="left", fill="x", expand=True, padx=10, pady=5)
disconnect_button = ttk.Button(conn_frame, text="Disconnect", command=disconnect_modbus, state="disabled")
disconnect_button.pack(side="left", fill="x", expand=True, padx=10, pady=5)

# --- Frame Kontrol ---
control_frame = ttk.LabelFrame(root, text="Kontrol Motor")
control_frame.pack(fill="x", padx=10, pady=5)

rpm_frame = ttk.Frame(control_frame)
rpm_frame.pack(pady=5)
ttk.Label(rpm_frame, text="Set RPM (Gunakan '-' untuk Mundur):").pack(side="top")

rpm_control_frame = ttk.Frame(rpm_frame)
rpm_control_frame.pack(side="top", pady=5)

rpm_down_btn = ttk.Button(rpm_control_frame, text="- 100", command=lambda: adjust_rpm(-RPM_STEP), width=6)
rpm_down_btn.pack(side="left", padx=5)

rpm_entry = ttk.Entry(rpm_control_frame, textvariable=rpm_var, width=10, justify="center")
rpm_entry.pack(side="left", padx=5)

rpm_up_btn = ttk.Button(rpm_control_frame, text="+ 100", command=lambda: adjust_rpm(RPM_STEP), width=6)
rpm_up_btn.pack(side="left", padx=5)

send_rpm_btn = ttk.Button(control_frame, text="Kirim RPM", command=send_rpm_command)
send_rpm_btn.pack(fill="x", padx=10, pady=2)

dir_frame = ttk.Frame(control_frame)
dir_frame.pack(fill="x", padx=5, pady=2)

ccw_btn = ttk.Button(dir_frame, text="Putar Kiri (CCW / Maju)", command=lambda: set_direction('ccw'))
ccw_btn.pack(side="left", fill="x", expand=True, padx=5)

cw_btn = ttk.Button(dir_frame, text="Putar Kanan (CW / Mundur)", command=lambda: set_direction('cw'))
cw_btn.pack(side="left", fill="x", expand=True, padx=5)

stop_btn = ttk.Button(control_frame, text="BERHENTI", command=stop_spindle)
stop_btn.pack(fill="x", padx=10, pady=(2, 10))

# --- Frame Status ---
status_frame = ttk.LabelFrame(root, text="Status")
status_frame.pack(fill="x", padx=10, pady=5)

status_conn_label = ttk.Label(status_frame, text="Status: Terputus", foreground="red", anchor="w")
status_conn_label.pack(fill="x", padx=10, pady=2)

actual_rpm_label = ttk.Label(status_frame, text="RPM Aktual: 0", anchor="w")
actual_rpm_label.pack(fill="x", padx=10, pady=2)

status_main_label = ttk.Label(status_frame, text="Status: Idle", anchor="w")
status_main_label.pack(fill="x", padx=10, pady=2)

# --- List Widget untuk Toggle ---
connection_widgets = [com_port_combo, baud_combo, parity_combo, stop_bits_combo]
control_widgets = [
    rpm_down_btn, rpm_entry, rpm_up_btn, send_rpm_btn,
    ccw_btn, cw_btn, stop_btn
]

# --- Inisialisasi GUI ---
toggle_controls(False)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
