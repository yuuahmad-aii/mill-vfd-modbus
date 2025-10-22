# perkenalan
ini adalah repo untuk riset modbus vfd untuk linux cnc

## pengaturan parameter driver mige
|no|no parameter|nama parameter|keterangan parameter|nilai set|
|---|---|---|---|---|
|1|P-004|Control Mode|Set to speed control mode|1|
|2|P-025|Source of speed command |Internal multi-step speed command|1|

## perintah modbus untuk driver mige
|no|no parameter|nama parameter|keterangan parameter|nilai set|
|---|---|---|---|---|
|1|P-098|Force enable|force enable signal from db port|1|
|2|P-098|Force enable|force disable signal from db port|0|
|3|P-122|Digital input DI forced valid parameter3|buat sinyal cw menjadi high|1|
|4|P-023|Digital input DI forced valid parameter4|buat sinyal ccw menjadi high|1|
|5|P-012|Digital input DI forced valid parameter3|buat sinyal cw menjadi low|0|
|5|P-012|Digital input DI forced valid parameter4|buat sinyal ccw menjadi low|0|

