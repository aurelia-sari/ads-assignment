/* Account & Dashboard session helper (student-4, Aurelia Sari).
 *
 * There's no server-side session store for this static-frontend + HTTP-API
 * stack, so the signed-in user is kept client-side in localStorage after
 * sign-in and cleared on sign-out. The source of truth for "is this user
 * currently signed in" stays server-side (access_logs.in_session, via
 * /api/student-4/auth/status/<id>) so other features can check it too, this
 * is just what lets a page know *which* user to ask about and to sign out.
 *
 * Include this script on any student-4 page, then call NextStopSession.*.
 */
(function (global) {
    const STORAGE_KEY = "nextstop_user";

    function saveSession(user) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    }

    function getSession() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (err) {
            return null;
        }
    }

    function clearSession() {
        localStorage.removeItem(STORAGE_KEY);
    }

    async function signOut(redirectTo) {
        const user = getSession();
        clearSession();

        if (user && user.id) {
            try {
                await fetch("/api/student-4/auth/logout", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: user.id }),
                });
            } catch (err) {
                // Session is cleared client-side regardless - the user is
                // signed out of this browser even if the server call failed.
            }
        }

        window.location.href = redirectTo || "signin.html";
    }

    function initSignOutButtons(redirectTo) {
        const buttons = document.querySelectorAll("[data-signout]");
        const signedIn = !!getSession();

        buttons.forEach((button) => {
            button.style.display = signedIn ? "" : "none";
            button.addEventListener("click", () => signOut(redirectTo));
        });
    }

    global.NextStopSession = {
        saveSession,
        getSession,
        clearSession,
        signOut,
        initSignOutButtons,
    };
})(window);
