_dst0:
    inc R0
    inc R1
    inc R2
    inc R3
    inc R4
    inc R5
    inc R6
    inc R7
    ljmp _dst1
    inc R0
    inc R0
_dst1:
    sjmp _dst3
    sjmp _dst0
    inc R0
    inc R1
    inc R2
    inc R3
    inc R4
    inc R5
_dst3:
    inc R6
    inc R7
    sjmp _dst3

;
;
;     inc R0
;     inc R1
;     inc R2
;     inc R3
;     inc R4
;     inc R5
;     inc R6
;     inc R7
;
;     sjmp _loop2
;     ; mul AB
;
; _loop1:
;     inc R7
;     inc R6
;     inc R5
;     inc R4
;     inc R3
;     inc R2
;     inc R1
;     inc R0
;
; _loop2:
;     inc R0
;     inc R1
;     inc R2
;     inc R3
;     inc R4
;     inc R5
;     inc R6
;     inc R7
;
; _loop0:
;     sjmp _loop1
