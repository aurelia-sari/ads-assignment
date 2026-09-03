/* Account & Dashboard session helper (student-4, Aurelia Sari).
 *
 * localStorage is used to remember which user this browser last signed in as
 * Whether that user is still signed in is decided server-side, from
 * access_logs.in_session via /api/student-4/auth/status/<id>, because
 * localStorage can be edited by anyone and must not be able to
 * grant a "signed in" state by itself.
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

    async function verifySession() {
        const user = getSession();
        if (!user || !user.id) {
            clearSession();
            return null;
        }

        try {
            const response = await fetch(`/api/student-4/auth/status/${user.id}`);
            if (!response.ok) {
                clearSession();
                return null;
            }
            const data = await response.json();
            if (!data.is_valid) {
                clearSession();
                return null;
            }
        } catch (err) {
            return null;
        }

        return user;
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
            }
        }

        sessionStorage.setItem("justLoggedOut", "1");
        window.location.href = redirectTo || "signin.html";
    }

    async function initSignOutButtons(redirectTo) {
        const buttons = document.querySelectorAll("[data-signout]");
        const signedIn = !!(await verifySession());

        buttons.forEach((button) => {
            button.style.display = signedIn ? "" : "none";
            button.addEventListener("click", () => signOut(redirectTo));
        });
    }

    global.NextStopSession = {
        saveSession,
        getSession,
        clearSession,
        verifySession,
        signOut,
        initSignOutButtons,
    };
})(window);
