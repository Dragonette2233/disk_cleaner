
model = None
p_info = 'CRC'
model = 'ST9000MN1'
is_sleep = True

match p_info, model, is_sleep:
    case p_info, model, 'IO':
        model = model + ' (I/O)'
        cclr = 'orange'
    case p_info, model, 'CONFLICT':
        model = model + ' (process conflict)'
        cclr = 'orange'
    case 'UL' | 'NL' | 'NC', 'Not connected' | "! Disconnected !", False:
        cclr = 'red'
    case 'EL', model, False:
        cclr = 'yellow'
    case 'NL', model, False:
        cclr = 'green'
    case 'CRC' | 'IO' | 'OUT' as e, model, True:
        model = model + f' ({e})'

print(model)