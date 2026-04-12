"use client";

import { useUserStore, removeFromWishlist, moveWishlistToCart } from "@/lib/userStore";

export default function WishlistPage() {
  const wishlist = useUserStore((s) => s.wishlist);

  function handleMoveToCart(course_id: string) {
    moveWishlistToCart(course_id);
  }

  function handleRemove(course_id: string) {
    removeFromWishlist(course_id);
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Wishlist</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Courses you might want to take later.
        </p>
      </div>

      {wishlist.length === 0 ? (
        <div className="text-center py-20 text-[var(--text-muted)]">
          <svg
            className="w-14 h-14 mx-auto mb-4 text-white/30"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
            />
          </svg>
          <p className="text-base font-medium">No wishlisted courses yet.</p>
          <p className="text-sm mt-1 max-w-sm mx-auto">
            Browse recommendations and bookmark courses you might take later.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {wishlist.map((courseId) => (
            <div
              key={courseId}
              className="bg-[var(--bg-secondary)] rounded-2xl p-5 border border-[var(--border-dark)] shadow-sm flex flex-col gap-4"
            >
              <div>
                <p className="text-lg font-bold font-mono text-[var(--text-primary)]">
                  {courseId}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleMoveToCart(courseId)}
                  className="flex-1 py-2 rounded-xl bg-[var(--umd-red)] text-white text-sm font-semibold hover:bg-[var(--umd-red)]/90 transition-colors"
                >
                  Move to Cart
                </button>
                <button
                  onClick={() => handleRemove(courseId)}
                  className="flex-1 py-2 rounded-xl border border-[var(--border-dark)] text-sm font-semibold text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
