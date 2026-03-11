      *================================================================*
      * BILLING.CBL  -  Legacy COBOL Billing System                  *
      * Written circa 1987 for IBM mainframe.                        *
      * Processes monthly utility bills for residential customers.   *
      * Business logic must be preserved exactly during migration.   *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BILLING.
       AUTHOR.     LEGACY-SYSTEMS-TEAM.
       DATE-WRITTEN. 1987-03-15.

      *----------------------------------------------------------------*
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-3090.
       OBJECT-COMPUTER. IBM-3090.

      *----------------------------------------------------------------*
       DATA DIVISION.
       WORKING-STORAGE SECTION.

       01  WS-CUSTOMER-RECORD.
           05  WS-CUST-ID          PIC X(10).
           05  WS-CUST-NAME        PIC X(30).
           05  WS-ACCOUNT-TYPE     PIC X(01).
               88  RESIDENTIAL     VALUE 'R'.
               88  COMMERCIAL      VALUE 'C'.

       01  WS-BILLING-DATA.
           05  WS-PREV-READING     PIC 9(07) VALUE ZEROS.
           05  WS-CURR-READING     PIC 9(07) VALUE ZEROS.
           05  WS-UNITS-USED       PIC 9(07) VALUE ZEROS.
           05  WS-BILL-AMOUNT      PIC 9(09)V99 VALUE ZEROS.
           05  WS-TAX-AMOUNT       PIC 9(07)V99 VALUE ZEROS.
           05  WS-TOTAL-DUE        PIC 9(09)V99 VALUE ZEROS.
           05  WS-LATE-CHARGE      PIC 9(05)V99 VALUE ZEROS.
           05  WS-IS-LATE          PIC X(01)    VALUE 'N'.

       01  WS-RATES.
           05  WS-RATE-PER-UNIT    PIC 9(03)V99 VALUE 5.75.
           05  WS-TAX-RATE         PIC V99      VALUE .08.
           05  WS-LATE-FEE-RATE    PIC V99      VALUE .15.
           05  WS-FIXED-CHARGE     PIC 9(04)V99 VALUE 25.00.
           05  WS-COMM-RATE-MULT   PIC 9(01)V9  VALUE 1.5.

       01  WS-RETURN-CODE          PIC 9(02)    VALUE 00.
           88  SUCCESS             VALUE 00.
           88  ERROR-ZERO-UNITS    VALUE 10.
           88  ERROR-INVALID-ACCT  VALUE 20.

      *----------------------------------------------------------------*
       PROCEDURE DIVISION.

      *================================================================*
       MAIN-PARA.
      *================================================================*
      *    Main entry point - orchestrates the full billing cycle
           PERFORM INITIALIZE-BILLING
           PERFORM CALC-UNITS-USED
           IF WS-UNITS-USED > ZEROS
               PERFORM CALC-BILL-AMOUNT
               PERFORM APPLY-TAX
               IF WS-IS-LATE = 'Y'
                   PERFORM APPLY-LATE-CHARGE
               END-IF
               PERFORM CALC-TOTAL-DUE
               PERFORM PRINT-BILL
           ELSE
               MOVE 10 TO WS-RETURN-CODE
               PERFORM PRINT-ZERO-USAGE-NOTICE
           END-IF
           STOP RUN.

      *================================================================*
       INITIALIZE-BILLING.
      *================================================================*
      *    Reset all working-storage before processing a new bill
           MOVE ZEROS TO WS-BILL-AMOUNT
           MOVE ZEROS TO WS-TAX-AMOUNT
           MOVE ZEROS TO WS-TOTAL-DUE
           MOVE ZEROS TO WS-LATE-CHARGE
           MOVE ZEROS TO WS-UNITS-USED
           MOVE 'N'   TO WS-IS-LATE
           MOVE 00    TO WS-RETURN-CODE.

      *================================================================*
       CALC-UNITS-USED.
      *================================================================*
      *    Compute electricity/utility units consumed this period
           IF WS-CURR-READING >= WS-PREV-READING
               SUBTRACT WS-PREV-READING FROM WS-CURR-READING
                   GIVING WS-UNITS-USED
           ELSE
      *         Meter rollover: meter maxed at 9999999 and reset to 0
               COMPUTE WS-UNITS-USED =
                   (9999999 - WS-PREV-READING) + WS-CURR-READING + 1
           END-IF.

      *================================================================*
       CALC-BILL-AMOUNT.
      *================================================================*
      *    Calculate base bill: fixed charge + (units * rate)
      *    Commercial accounts pay 1.5x the standard rate
           MOVE WS-FIXED-CHARGE TO WS-BILL-AMOUNT
           IF COMMERCIAL
               COMPUTE WS-BILL-AMOUNT = WS-FIXED-CHARGE +
                   (WS-UNITS-USED * WS-RATE-PER-UNIT * WS-COMM-RATE-MULT)
           ELSE
               COMPUTE WS-BILL-AMOUNT = WS-FIXED-CHARGE +
                   (WS-UNITS-USED * WS-RATE-PER-UNIT)
           END-IF.

      *================================================================*
       APPLY-TAX.
      *================================================================*
      *    Compute and add sales tax on the bill amount
           COMPUTE WS-TAX-AMOUNT ROUNDED =
               WS-BILL-AMOUNT * WS-TAX-RATE.

      *================================================================*
       APPLY-LATE-CHARGE.
      *================================================================*
      *    Add a late payment penalty (15% of bill) if payment overdue
           COMPUTE WS-LATE-CHARGE ROUNDED =
               WS-BILL-AMOUNT * WS-LATE-FEE-RATE.

      *================================================================*
       CALC-TOTAL-DUE.
      *================================================================*
      *    Sum all charges into the final amount due
           COMPUTE WS-TOTAL-DUE =
               WS-BILL-AMOUNT + WS-TAX-AMOUNT + WS-LATE-CHARGE.

      *================================================================*
       PRINT-BILL.
      *================================================================*
      *    Output the formatted customer bill to print spool
           DISPLAY '========================================'
           DISPLAY 'UTILITY BILL STATEMENT'
           DISPLAY 'Customer ID  : ' WS-CUST-ID
           DISPLAY 'Customer Name: ' WS-CUST-NAME
           DISPLAY 'Account Type : ' WS-ACCOUNT-TYPE
           DISPLAY 'Prev Reading : ' WS-PREV-READING
           DISPLAY 'Curr Reading : ' WS-CURR-READING
           DISPLAY 'Units Used   : ' WS-UNITS-USED
           DISPLAY 'Base Charge  : $' WS-BILL-AMOUNT
           DISPLAY 'Tax (8%)     : $' WS-TAX-AMOUNT
           DISPLAY 'Late Charge  : $' WS-LATE-CHARGE
           DISPLAY '----------------------------------------'
           DISPLAY 'TOTAL DUE    : $' WS-TOTAL-DUE
           DISPLAY '========================================'.

      *================================================================*
       PRINT-ZERO-USAGE-NOTICE.
      *================================================================*
      *    Notify when no units were consumed (possible meter fault)
           DISPLAY 'NOTICE: Zero units detected for ' WS-CUST-ID
           DISPLAY 'Please verify meter readings.'.

      *================================================================*
      * DEAD PARAGRAPHS - These are never PERFORMed from anywhere.
      * They should be detected and excluded from LLM context.
      *================================================================*
       OLD-RATE-CALC.
      *    Deprecated: used old tiered rate system removed in 1995
           COMPUTE WS-BILL-AMOUNT = WS-UNITS-USED * 3.25.

       DEBUG-DUMP-STORAGE.
      *    Temporary debug paragraph - was used during testing in 1988
           DISPLAY 'DEBUG BALANCE: ' WS-BILL-AMOUNT
           DISPLAY 'DEBUG UNITS  : ' WS-UNITS-USED.

       LEGACY-PAPER-REPORT.
      *    Replaced by PRINT-BILL in 1990. Kept for historical reference.
           DISPLAY 'REPORT: ' WS-CUST-ID ' OWES ' WS-TOTAL-DUE.
