"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUserStore, removeFromCart, clearCart } from "@/lib/userStore";

export default function CartDrawer({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const cart = useUserStore((s) => s.cart);
  const router = useRouter();

  function handleRemove(course_id: string) {
    removeFromCart(course_id);
  }

  function handleClear() {
    clearCart();
  }

  function buildSchedule() {
    const ids = cart.join(",");
    router.push(`/schedule?courses=${ids}`);
    onClose();
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-80 bg-[var(--bg-secondary)] z-50 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[var(--text-primary)]">Planning Cart</span>
            <span
              className="text-white text-xs font-bold px-2 py-0.5 rounded-full"
              style={{ backgroundColor: "#e21833" }}
            >
              {cart.length}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-[var(--text-muted)] text-xl font-light leading-none"
          >
            ✕
          </button>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
          {cart.length === 0 && (
            <div className="text-center py-12">
              <p className="text-white/40 text-sm">Your cart is empty.</p>
              <p className="text-white/30 text-xs mt-1">
                Add courses from recommendations or course pages.
              </p>
            </div>
          )}

          {cart.map((courseId) => (
            <div
              key={courseId}
              className="flex items-center justify-between bg-[var(--bg-elevated)] rounded-lg px-4 py-3"
            >
              <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                {courseId}
              </span>
              <button
                onClick={() => handleRemove(courseId)}
                className="text-white/30 hover:text-red-500 text-sm transition-colors"
              >
                Remove
              </button>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t space-y-3">
          {cart.length > 0 && (
            <>
              <p className="text-xs text-white/40 text-center">
                {cart.length} course{cart.length !== 1 ? "s" : ""} selected
              </p>
              <button
                onClick={buildSchedule}
                className="w-full py-3 rounded-xl font-semibold text-white text-sm transition-colors hover:opacity-90"
                style={{ backgroundColor: "#e21833" }}
              >
                Build Schedule →
              </button>
              <button
                onClick={handleClear}
                className="w-full py-2 rounded-xl text-sm text-white/40 hover:text-[var(--text-muted)] transition-colors"
              >
                Clear Cart
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}
