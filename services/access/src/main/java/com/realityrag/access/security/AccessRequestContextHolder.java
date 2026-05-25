package com.realityrag.access.security;

public final class AccessRequestContextHolder {
    private static final ThreadLocal<AccessRequestContext> HOLDER = new ThreadLocal<>();

    private AccessRequestContextHolder() {}

    public static void set(AccessRequestContext context) {
        HOLDER.set(context);
    }

    public static AccessRequestContext get() {
        return HOLDER.get();
    }

    public static void clear() {
        HOLDER.remove();
    }
}
