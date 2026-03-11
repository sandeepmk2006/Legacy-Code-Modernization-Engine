package com.legacy.banking;

import java.util.ArrayList;
import java.util.List;

/**
 * TransactionValidator — Legacy utility class called by CustomerProcessor.
 * Performs validation rules on monetary transactions.
 * Written circa 2001.
 */
public class TransactionValidator {

    private static final double MAX_SINGLE_TRANSACTION = 500_000.00;
    private static final double MIN_TRANSACTION        = 0.01;
    private static final int    MAX_DAILY_TXNS         = 100;

    private List dailyLog;   // pre-generics List

    public TransactionValidator() {
        this.dailyLog = new ArrayList();
    }

    /**
     * Master validation: checks amount range, daily limit, and fraud score.
     * Returns true if the transaction is allowed to proceed.
     */
    public boolean isValid(double amount, String type) {
        if (!isAmountInRange(amount)) {
            return false;
        }
        if (!isDailyLimitOk()) {
            return false;
        }
        if (isFraudulent(amount, type)) {
            return false;
        }
        dailyLog.add(type + ":" + amount);
        return true;
    }

    /**
     * Checks that the transaction amount is within allowed bounds.
     */
    private boolean isAmountInRange(double amount) {
        return amount >= MIN_TRANSACTION && amount <= MAX_SINGLE_TRANSACTION;
    }

    /**
     * Ensures the customer has not exceeded their daily transaction count.
     */
    private boolean isDailyLimitOk() {
        return dailyLog.size() < MAX_DAILY_TXNS;
    }

    /**
     * Simple rule-based fraud check.
     * Flags round-number withdrawals over $10,000 as suspicious.
     */
    private boolean isFraudulent(double amount, String type) {
        if ("WITHDRAW".equals(type) && amount >= 10000.0) {
            // Check for round-number pattern (potential structuring)
            return (amount % 1000.0 == 0.0);
        }
        return false;
    }

    /**
     * Resets the daily transaction log at midnight (called by scheduler).
     */
    public void resetDaily() {
        dailyLog.clear();
    }

    /**
     * Returns the number of transactions logged today.
     */
    public int getDailyCount() {
        return dailyLog.size();
    }

    // ------------------------------------------------------------------
    // DEAD CODE — never called, excluded from LLM context automatically
    // ------------------------------------------------------------------

    /** @deprecated Replaced by isFraudulent() in 1998 */
    private boolean oldFraudCheck(double amount) {
        return amount > 99999.99;
    }

    /** @deprecated Was used in early testing only */
    private void printDebugLog() {
        for (int i = 0; i < dailyLog.size(); i++) {
            System.out.println("[DEBUG] " + dailyLog.get(i));
        }
    }
}
