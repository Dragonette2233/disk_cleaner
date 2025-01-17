import os
import subprocess

SMART_CTL_EX = os.path.join('.', 'smartmontools', 'bin', 'smartctl.exe')

def _build_smart():
    # return short str: 0p0u0 | long str: Power time, Relocated, Pendigs, Uncorrectable
    ...

def get_short_smarts(disk_num=False, timeout=4):
    # Return SMART data like 0p0u0 (0 bads, 0 pendings, 0 uncorrectable)
    smarts_short = []   
    smarts_complex = []
    
    for i in range(10):
        try:
            # Используем subprocess.run для добавления таймаута
            process = subprocess.run(
                f'"{SMART_CTL_EX}" -A /dev/pd{i}',  # Enclose the path in quotes to handle spaces
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
                timeout=timeout  # Устанавливаем таймаут в секундах
            )
            stdout = process.stdout
        except subprocess.TimeoutExpired:
            # Обработка таймаута: добавляем "!timeout" в результаты
            smarts_short.append("!timeout")
            smarts_complex.append("!timeout")
            continue

        strings = stdout.split('\n')

        smart_short_view = []
        smart_complex_view = []

        for line in strings:
            line_as_list = line.split()
            
            # print(line_as_list)
            if line_as_list:
                
                if line_as_list[0] in ('1', '4', '5', '9', '197', '198', '199'):
                    # print(len(line_as_list))
                        
                    match line_as_list[0]:
                        case '5':
                            smart_short_view.append(line_as_list[9])
                            smart_complex_view.append(f"Relocated -- {line_as_list[9]}")
                        case '197':
                            smart_short_view.append('p' + line_as_list[9])
                            smart_complex_view.append(f"Current pending -- {line_as_list[9]}")
                        case '198':
                            smart_short_view.append('u' + line_as_list[9])
                            smart_complex_view.append(f"Offline uncorrectable -- {line_as_list[9]}")
                        case '199':
                            smart_complex_view.append(f"Ultra DMA CRC -- {line_as_list[9]}")
                        case '9':
                            smart_complex_view.insert(0, f"Power on hours -- {line_as_list[9]}")
        
        
        short_string = ''.join(i for i in smart_short_view)
        # print(short_string)
        complex_string = '\n'.join(i for i in smart_complex_view)
        
        smarts_short.append(short_string)
        smarts_complex.append(complex_string)
    
    return [smarts_short, smarts_complex]
