
def patch_file(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        if old not in content:
            print(f"FAILED TO FIND in {path}:\n{old[:100]}...\n")
        else:
            content = content.replace(old, new)
            print(f"Patched in {path}:\n{old[:100]}...\n")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

replacements_expr = []

# ListLiteral
old_list_literal = """    if node.kind == "ListLiteral" {
        cap = len(node.args)
        ptr_sz = ptr_size(state)
        total_sz = 1048576
        
        req_sz = 16 + (cap * ptr_sz)
        if req_sz > total_sz {
            total_sz = req_sz
        }
        
        emit(state, "    push " + str(total_sz))
        emit(state, "    call _malloc")
        clean_n(state, 1)
        
        emit(state, "    mov dword ptr [%a], " + str(len(node.args)))
        emit(state, "    mov dword ptr [%a+8], " + str(total_sz))
        emit(state, "    push %a")
        
        idx_list = 0
        while idx_list < len(node.args) {
            compile_expr(state, node.args[idx_list])
            emit(state, "    pop %c")
            emit(state, "    pop %a")
            
            data_off = 16 + (idx_list * ptr_sz)
            if ptr_sz == 8 {
                emit(state, "    mov [%a + " + str(data_off) + "], rcx")
            } else {
                emit(state, "    mov [%a + " + str(data_off) + "], ecx")
            }
            emit(state, "    push %a")
            idx_list = idx_list + 1
        }
    }"""
new_list_literal = """    if node.kind == "ListLiteral" {
        n = len(node.args)
        ptr_sz = ptr_size(state)
        req_cap = 16
        if n > 0 {
            req_cap = n * ptr_sz
        }
        emit(state, "    push 16")
        emit(state, "    call _malloc")
        clean_n(state, 1)
        emit(state, "    push %a")
        emit(state, "    push " + str(req_cap))
        emit(state, "    call _malloc")
        clean_n(state, 1)
        emit(state, "    pop %x")
        emit(state, "    push %x")
        emit(state, "    mov dword ptr [%x], " + str(n))
        emit(state, "    mov dword ptr [%x+4], " + str(req_cap))
        emit(state, "    mov [%x+8], %a")
        idx_list = 0
        while idx_list < len(node.args) {
            emit(state, "    push %x")
            compile_expr(state, node.args[idx_list])
            emit(state, "    pop %a")
            emit(state, "    pop %x")
            emit(state, "    mov %d, [%x+8]")
            data_off = idx_list * ptr_sz
            if ptr_sz == 8 {
                emit(state, "    mov [%d + " + str(data_off) + "], rcx")
            } else {
                emit(state, "    mov [%d + " + str(data_off) + "], ecx")
            }
            idx_list = idx_list + 1
        }
    }"""
replacements_expr.append((old_list_literal, new_list_literal))

# ArrayIndex
old_array_index = """        } else {
            ptr_sz = ptr_size(state)
            emit(state, "    lea %a, [%d + 16]")
            if ptr_sz == 8 {
                emit(state, "    mov %a, [%a + %c*8]")
            } else {
                emit(state, "    mov %a, [%a + %c*4]")
            }
            emit(state, "    push %a")
        }"""
new_array_index = """        } else {
            ptr_sz = ptr_size(state)
            emit(state, "    mov %d, [%d + 8]")
            if ptr_sz == 8 {
                emit(state, "    mov %a, [%d + %c*8]")
            } else {
                emit(state, "    mov %a, [%d + %c*4]")
            }
            emit(state, "    push %a")
        }"""
replacements_expr.append((old_array_index, new_array_index))

# Len
old_len_list = """        if use_strlen == 1 {
            emit(state, "    call _strlen")
            clean_n(state, 1)
            emit(state, "    push %a")
        } else {
            emit(state, "    pop %a")
            emit(state, "    mov eax, dword ptr [%a]")
            emit(state, "    push %a")
        }"""
new_len_list = """        if use_strlen == 1 {
            emit(state, "    call _strlen")
            clean_n(state, 1)
            emit(state, "    push %a")
        } else {
            emit(state, "    pop %a")
            emit(state, "    mov eax, dword ptr [%a]")
            emit(state, "    push %a")
        }"""
# wait, len doesn't change since count is at offset 0 in both old and new. So I don't need to change `len`.

# Append
old_append = """        if node.val_str == "append" {
            compile_expr(state, node.args[0])
            compile_expr(state, node.left)
            emit(state, "    pop %x")
            emit(state, "    pop %c")
            ptr_sz = ptr_size(state)
            emit(state, "    mov eax, dword ptr [%x]")
            emit(state, "    mov edx, eax")
            emit(state, "    add edx, 1")
            if ptr_sz == 8 {
                emit(state, "    shl edx, 3")
            } else {
                emit(state, "    shl edx, 2")
            }
            emit(state, "    add edx, 16")
            emit(state, "    mov esi, dword ptr [%x+8]")
            emit(state, "    cmp edx, esi")
            no_realloc = next_label(state, "L_no_realloc")
            emit(state, "    jle " + no_realloc)
            
            emit(state, "    shl esi, 1")
            emit(state, "    push %x")
            emit(state, "    push %c")
            if is_x64(state) {
                emit(state, "    mov %j, %x")
                emit(state, "    sub %s, 32")
                emit(state, "    call _realloc")
                emit(state, "    add %s, 32")
            } else {
                emit(state, "    push %i")
                emit(state, "    push %x")
                emit(state, "    call _realloc")
                clean_n(state, 2)
            }
            emit(state, "    pop %c")
            emit(state, "    pop %x")
            emit(state, "    mov %x, %a")
            emit(state, "    mov dword ptr [%x+8], esi")
            
            emit(state, no_realloc + ":")
            emit(state, "    mov eax, dword ptr [%x]")
            emit(state, "    lea %d, [%x + 16]")
            if ptr_sz == 8 {
                emit(state, "    mov [%d + %a*8], %c")
            } else {
                emit(state, "    mov [%d + %a*4], %c")
            }
            emit(state, "    add eax, 1")
            emit(state, "    mov dword ptr [%x], eax")
            emit(state, "    push 0")
        }"""
new_append = """        if node.val_str == "append" {
            compile_expr(state, node.args[0])
            compile_expr(state, node.left)
            emit(state, "    pop %x")
            emit(state, "    pop %c")
            ptr_sz = ptr_size(state)
            emit(state, "    mov eax, dword ptr [%x]")
            emit(state, "    mov edx, eax")
            emit(state, "    add edx, 1")
            if ptr_sz == 8 {
                emit(state, "    shl edx, 3")
            } else {
                emit(state, "    shl edx, 2")
            }
            emit(state, "    mov esi, dword ptr [%x+4]")
            emit(state, "    cmp edx, esi")
            no_realloc = next_label(state, "L_no_realloc")
            emit(state, "    jle " + no_realloc)
            
            emit(state, "    shl esi, 1")
            emit(state, "    push %x")
            emit(state, "    push %c")
            if is_x64(state) {
                emit(state, "    mov %j, [%x+8]")
                emit(state, "    sub %s, 32")
                emit(state, "    call _realloc")
                emit(state, "    add %s, 32")
            } else {
                emit(state, "    push %i")
                emit(state, "    mov %d, [%x+8]")
                emit(state, "    push %d")
                emit(state, "    call _realloc")
                clean_n(state, 2)
            }
            emit(state, "    pop %c")
            emit(state, "    pop %x")
            emit(state, "    mov [%x+8], %a")
            emit(state, "    mov dword ptr [%x+4], esi")
            
            emit(state, no_realloc + ":")
            emit(state, "    mov eax, dword ptr [%x]")
            emit(state, "    mov %d, [%x+8]")
            if ptr_sz == 8 {
                emit(state, "    mov [%d + %a*8], %c")
            } else {
                emit(state, "    mov [%d + %a*4], %c")
            }
            emit(state, "    add eax, 1")
            emit(state, "    mov dword ptr [%x], eax")
            emit(state, "    push 0")
        }"""
replacements_expr.append((old_append, new_append))

# Pop
old_pop = """        if node.val_str == "pop" {
            compile_expr(state, node.left)
            emit(state, "    pop %x")
            ptr_sz = ptr_size(state)
            emit(state, "    mov eax, dword ptr [%x]")
            emit(state, "    sub eax, 1")
            emit(state, "    mov dword ptr [%x], eax")
            emit(state, "    lea %d, [%x + 16]")
            if ptr_sz == 8 {
                emit(state, "    mov %c, [%d + %a*8]")
            } else {
                emit(state, "    mov %c, [%d + %a*4]")
            }
            emit(state, "    push %c")
        }"""
new_pop = """        if node.val_str == "pop" {
            compile_expr(state, node.left)
            emit(state, "    pop %x")
            ptr_sz = ptr_size(state)
            emit(state, "    mov eax, dword ptr [%x]")
            emit(state, "    sub eax, 1")
            emit(state, "    mov dword ptr [%x], eax")
            emit(state, "    mov %d, [%x+8]")
            if ptr_sz == 8 {
                emit(state, "    mov %c, [%d + %a*8]")
            } else {
                emit(state, "    mov %c, [%d + %a*4]")
            }
            emit(state, "    push %c")
        }"""
replacements_expr.append((old_pop, new_pop))


patch_file('d:/Coding/Python/Random Topic Practice/panda panda/nova/stdlib/backend/x86_64/codegen_expr.nv', replacements_expr)

# Now for ForIn in codegen_stmt.nv
with open('d:/Coding/Python/Random Topic Practice/panda panda/nova/stdlib/backend/x86_64/codegen_stmt.nv', 'r', encoding='utf-8') as f:
    stmt_content = f.read()

replacements_stmt = []
old_for_in = """    if node.kind == "ForIn" {
        loop_label = next_label(state, "L_forin")
        end_label = next_label(state, "L_forin_end")
        
        push_loop_labels(state, loop_label, end_label)
        
        compile_expr(state, node.left) # collection
        emit(state, "    pop %d")
        emit(state, "    mov eax, [%d]")
        emit(state, "    push %a")
        emit(state, "    xor eax, eax")
        
        offset_idx = get_local_offset(state, node.val_str)
        emit(state, "    mov " + fmt_local(state, offset_idx) + ", eax")
        
        emit(state, loop_label + ":")
        
        emit(state, "    mov eax, " + fmt_local(state, offset_idx))
        emit(state, "    pop %x")
        emit(state, "    push %x")
        emit(state, "    cmp eax, ebx")
        emit(state, "    jge " + end_label)
        
        emit(state, "    lea %a, [%d + 16]")
        emit(state, "    mov ecx, " + fmt_local(state, offset_idx))
        ptr_sz = ptr_size(state)
        if ptr_sz == 8 {
            emit(state, "    mov eax, [%a + %c*8]")
        } else {
            emit(state, "    mov eax, [%a + %c*4]")
        }
        
        emit(state, "    mov " + fmt_local(state, 8) + ", eax")
        emit(state, "    push %a")
        
        idx = 0
        while idx < len(node.body) {
            compile_stmt(state, node.body[idx])
            idx = idx + 1
        }
        
        emit(state, "    inc dword ptr " + fmt_local(state, offset_idx))
        emit(state, "    jmp " + loop_label)
        
        emit(state, end_label + ":")
        clean_n(state, 1)
        
        pop_loop_labels(state)
    }"""
new_for_in = """    if node.kind == "ForIn" {
        loop_label = next_label(state, "L_forin")
        end_label = next_label(state, "L_forin_end")
        
        push_loop_labels(state, loop_label, end_label)
        
        compile_expr(state, node.left) # collection
        emit(state, "    pop %d")
        emit(state, "    mov eax, [%d]")
        emit(state, "    push %a")
        emit(state, "    xor eax, eax")
        
        offset_idx = get_local_offset(state, node.val_str)
        emit(state, "    mov " + fmt_local(state, offset_idx) + ", eax")
        
        emit(state, loop_label + ":")
        
        emit(state, "    mov eax, " + fmt_local(state, offset_idx))
        emit(state, "    pop %x")
        emit(state, "    push %x")
        emit(state, "    cmp eax, ebx")
        emit(state, "    jge " + end_label)
        
        emit(state, "    mov %a, [%d + 8]")
        emit(state, "    mov ecx, " + fmt_local(state, offset_idx))
        ptr_sz = ptr_size(state)
        if ptr_sz == 8 {
            emit(state, "    mov %a, [%a + %c*8]")
        } else {
            emit(state, "    mov %a, [%a + %c*4]")
        }
        
        emit(state, "    mov " + fmt_local(state, 8) + ", eax")
        emit(state, "    push %a")
        
        idx = 0
        while idx < len(node.body) {
            compile_stmt(state, node.body[idx])
            idx = idx + 1
        }
        
        emit(state, "    inc dword ptr " + fmt_local(state, offset_idx))
        emit(state, "    jmp " + loop_label)
        
        emit(state, end_label + ":")
        clean_n(state, 1)
        
        pop_loop_labels(state)
    }"""
replacements_stmt.append((old_for_in, new_for_in))

patch_file('d:/Coding/Python/Random Topic Practice/panda panda/nova/stdlib/backend/x86_64/codegen_stmt.nv', replacements_stmt)
