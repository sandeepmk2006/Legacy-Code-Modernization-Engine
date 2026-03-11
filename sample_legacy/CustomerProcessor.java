package com.legacy.banking;

import java.util.ArrayList;
import java.util.Date;
import java.util.List;

/**
 * CustomerProcessor - Legacy Java 1.4 banking system.
 * Written circa 2003. Manages customer accounts and interest calculations.
 * NOTE: All business logic must be preserved exactly during modernization.
 */
public class CustomerProcessor {

    // Interest rate constants (annual)
    private static final double SAVINGS_RATE    = 0.035;
    private static final double CHECKING_RATE   = 0.005;
    private static final double PENALTY_RATE    = 0.18;

    private String customerId;
    private double balance;
    private String accountType;  // "SAVINGS" or "CHECKING"
    private boolean isOverdrawn;
    private List transactions;   // raw List (pre-generics)

    public CustomerProcessor(String customerId, String accountType) {
        this.customerId  = customerId;
        this.accountType = accountType;
        this.balance     = 0.0;
        this.isOverdrawn = false;
        this.transactions = new ArrayList();
    }

    /**
     * Main entry point - processes a batch of customer transactions
     * for end-of-day settlement.
     */
    public static void main(String[] args) {
        CustomerProcessor proc = new CustomerProcessor("CUST-001", "SAVINGS");
        proc.deposit(10000.00);
        proc.deposit(5000.00);
        proc.withdraw(2000.00);
        proc.applyMonthlyInterest();
        proc.generateStatement();
    }

    /**
     * Deposits money into account. No-op on negative amounts.
     */
    public void deposit(double amount) {
        if (amount <= 0) {
            logTransaction("DEPOSIT_REJECTED", amount);
            return;
        }
        balance = balance + amount;
        isOverdrawn = false;
        logTransaction("DEPOSIT", amount);
    }

    /**
     * Withdraws money. Applies overdraft penalty if balance goes negative.
     */
    public void withdraw(double amount) {
        if (amount <= 0) {
            logTransaction("WITHDRAW_REJECTED", amount);
            return;
        }
        balance = balance - amount;
        if (balance < 0) {
            isOverdrawn = true;
            applyOverdraftPenalty();
        }
        logTransaction("WITHDRAW", amount);
    }

    /**
     * Computes monthly interest and credits account.
     * SAVINGS accounts earn SAVINGS_RATE / 12 per month.
     * CHECKING accounts earn CHECKING_RATE / 12 per month.
     * Overdrawn accounts receive NO interest.
     */
    public void applyMonthlyInterest() {
        if (isOverdrawn) {
            logTransaction("INTEREST_SKIPPED_OVERDRAWN", 0.0);
            return;
        }
        double monthlyRate  = calculateMonthlyRate();
        double interestAmt  = calculateInterest(balance, monthlyRate);
        balance = balance + interestAmt;
        logTransaction("INTEREST_CREDIT", interestAmt);
    }

    /**
     * Calculates monthly rate from annual rate based on account type.
     */
    private double calculateMonthlyRate() {
        double annualRate;
        if ("SAVINGS".equals(accountType)) {
            annualRate = SAVINGS_RATE;
        } else {
            annualRate = CHECKING_RATE;
        }
        return annualRate / 12.0;
    }

    /**
     * Core interest calculation: principal * rate (simple interest).
     */
    private double calculateInterest(double principal, double rate) {
        return principal * rate;
    }

    /**
     * Applies flat overdraft penalty fee to the balance.
     */
    private void applyOverdraftPenalty() {
        double penalty = Math.abs(balance) * PENALTY_RATE;
        balance = balance - penalty;
        logTransaction("OVERDRAFT_PENALTY", penalty);
    }

    /**
     * Prints a formatted account statement to stdout.
     */
    public void generateStatement() {
        System.out.println("====================================");
        System.out.println("ACCOUNT STATEMENT");
        System.out.println("Customer ID : " + customerId);
        System.out.println("Account Type: " + accountType);
        System.out.println("Balance     : $" + formatCurrency(balance));
        System.out.println("Overdrawn   : " + (isOverdrawn ? "YES" : "NO"));
        System.out.println("Transactions: " + transactions.size());
        System.out.println("====================================");
        printTransactionHistory();
    }

    /**
     * Formats a double to 2 decimal places as a currency string.
     */
    private String formatCurrency(double amount) {
        // Old-school formatting, pre-String.format
        long cents = Math.round(amount * 100);
        long dollars = cents / 100;
        long remainCents = Math.abs(cents % 100);
        String centsStr = (remainCents < 10 ? "0" : "") + remainCents;
        return dollars + "." + centsStr;
    }

    /**
     * Prints all transactions in the log.
     */
    private void printTransactionHistory() {
        for (int i = 0; i < transactions.size(); i++) {
            System.out.println("  " + transactions.get(i));
        }
    }

    /**
     * Records a transaction entry in the transaction log.
     */
    private void logTransaction(String type, double amount) {
        String entry = new Date().toString() + " | " + type + " | $" + amount;
        transactions.add(entry);
    }

    // ---------------------------------------------------------------
    // DEAD CODE — these methods are unused, never called from anywhere.
    // They should be detected and excluded from LLM context.
    // ---------------------------------------------------------------

    /** @deprecated Never called - legacy migration placeholder */
    private void migrateToNewSystem() {
        // TODO: Remove in v2.0
        System.out.println("Migration not implemented");
    }

    /** @deprecated Unused debug method */
    private void debugDump() {
        System.out.println("DEBUG: balance=" + balance);
    }

    /** @deprecated Replaced by generateStatement() in 2001 */
    private void oldPrintReport() {
        System.out.println("OLD REPORT: " + customerId + " " + balance);
    }
}
