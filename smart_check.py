import os
import subprocess
import json

SMART_CTL_EX = os.path.join('.', 'smartmontools', 'bin', 'smartctl.exe')

def get_sas_smart(disk_num, strings, timeout=4):
    
    # try:
    #     # Используем subprocess.run для добавления таймаута
    #     process = subprocess.run(
    #         f'"{SMART_CTL_EX}" -j -l error /dev/pd{disk_num}',  # Enclose the path in quotes to handle spaces
    #         stdin=subprocess.PIPE,
    #         stdout=subprocess.PIPE,
    #         stderr=subprocess.PIPE,
    #         text=True,
    #         shell=True,
    #         timeout=timeout  # Устанавливаем таймаут в секундах
    #     )
    #     stdout = process.stdout
    # except subprocess.TimeoutExpired:
    #     ...
    
    # result = json.loads(stdout)

    status = strings['smartctl']['exit_status']


    if status not in (0, 8):
        return (1, 1)


    try:
        errors = strings['scsi_error_counter_log']
    except KeyError:
        return (1, 1)

    read_e = errors['read']
    write_e = errors['write']

    r_corr = read_e['total_errors_corrected']
    r_uncorr = read_e['total_uncorrected_errors']
    w_corr = write_e['total_errors_corrected']
    w_uncorr = write_e['total_uncorrected_errors']

    log_short = f"wu{w_uncorr}ru{r_uncorr}"
    log_complex = [
        "Read/Write Errors",
        "-----------------",
        f"Write Uncorrected - {w_uncorr}",
        f"Read Uncorrected - {r_uncorr}",
        f"Write Corrected - {w_corr}",
        f"Read Corrected - {r_corr}",   
    ]

    if status == 8 or strings["smart_status"]["passed"] is False:
        smart_status = strings["smart_status"]["scsi"]
        asc = smart_status['asc']
        ascq = smart_status['ascq']
        message = smart_status['ie_string']
        log_complex.append(f"Disk malfunction: ASC/ASCQ - {asc}/{ascq} | {message}")

    return [log_short, log_complex]

def get_short_smarts(disk_num=False, timeout=6):


    # Return SMART data like 0p0u0 (0 bads, 0 pendings, 0 uncorrectable)
    smarts_short = []
    smarts_complex = []
    
    for i in range(10):

        # first trying SAS smart
        # sm_short, sm_complex = get_sas_smart(i)

        # if (sm_short, sm_complex) != (1, 1):
        #     smarts_short.append(sm_short)
        #     smarts_complex.append('\n'.join(sm_complex))
        #     print('con')
        #     continue

        try:
            # Используем subprocess.run для добавления таймаута
            process = subprocess.run(
                f'"{SMART_CTL_EX}" -j -a /dev/pd{i}',  # Enclose the path in quotes to handle spaces
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
            smarts_short.append((i, "!timeout"))
            smarts_complex.append((i, "!timeout"))
            continue

        strings = json.loads(stdout)

        if not strings.get('ata_smart_attributes'):
            sm_short, sm_complex = get_sas_smart(i, strings)
            # print(sm_short,  f"of {i}")
            if sm_short  != 1:
                smarts_short.append((i, sm_short))
                smarts_complex.append((i, '\n'.join(sm_complex)))
            continue

        # print(i)
        # print(strings.keys())

        smart_short_view = []
        smart_complex_view = []
        try:
            sm_ = strings['ata_smart_attributes']['table']

            for s in sm_:
                raw_value = s['raw']['string']
                match s['id']:
                    case 5:
                        if len(raw_value.split()) > 1:
                            raw_value = raw_value[0]
                        smart_short_view.append(raw_value)
                        smart_complex_view.append(f"Relocated -- {raw_value}")
                    case 197:
                        smart_short_view.append('p' + raw_value)
                        smart_complex_view.append(f"Current pending -- {raw_value}")
                    case 198:
                        smart_short_view.append('u' + raw_value)
                        smart_complex_view.append(f"Offline uncorrectable -- {raw_value}")
                    case 199:
                        smart_complex_view.append(f"Ultra DMA CRC -- {raw_value}")
                    case 9:
                        smart_complex_view.insert(0, f"Power on hours -- {raw_value}")
                    case 171: #nand write
                        smart_short_view.append('nw' + raw_value)
                        smart_complex_view.append(f'NAND Write fail count -- {raw_value}')
                    case 172: # nand erase
                        smart_short_view.append('ne' + raw_value)
                        smart_complex_view.append(f'NAND Erase fail count -- {raw_value}')
                    case 187:
                        smart_short_view.append('re' + raw_value)
                        smart_complex_view.append(f'Uncorrectable errors -- {raw_value}')
                    case 231:
                        smart_short_view.append('lf' + raw_value)
                        smart_complex_view.append(f"SSD life left / Percentage used -- {raw_value}")
            # print(sm_)
        except KeyError:
            ...

        # for line in strings:
        #     line_as_list = line.split()
            
        #     # print(line_as_list)
        #     if line_as_list:
                
        #         if line_as_list[0] in ('1', '4', '5', '9', '197', '198', '199'):
        #             # print(len(line_as_list))
                        
        #             match line_as_list[0]:
        #                 case '5':
        #                     smart_short_view.append(line_as_list[9])
        #                     smart_complex_view.append(f"Relocated -- {line_as_list[9]}")
        #                 case '197':
        #                     smart_short_view.append('p' + line_as_list[9])
        #                     smart_complex_view.append(f"Current pending -- {line_as_list[9]}")
        #                 case '198':
        #                     smart_short_view.append('u' + line_as_list[9])
        #                     smart_complex_view.append(f"Offline uncorrectable -- {line_as_list[9]}")
        #                 case '199':
        #                     smart_complex_view.append(f"Ultra DMA CRC -- {line_as_list[9]}")
        #                 case '9':
        #                     smart_complex_view.insert(0, f"Power on hours -- {line_as_list[9]}")
        
        
        short_string = ''.join(i for i in smart_short_view)
        # print(short_string)
        complex_string = '\n'.join(i for i in smart_complex_view)
        
        smarts_short.append((i, short_string))
        smarts_complex.append((i, complex_string))
    
    return [smarts_short, smarts_complex]

