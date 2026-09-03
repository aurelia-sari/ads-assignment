/* 
 * Guard every page except the auth pages (sign-in, sign-up,
 * verify-pending) requires a valid NextStop session. Depends on
 * NextStopSession (student-4/session.js) being loaded first.
 */
(function (global) {
    const PUBLIC_PATHS = [
        "/student-4/signin.html",
        "/student-4/signup.html",
        "/student-4/verify-pending.html",
    ];

    function isPublicPath(pathname) {
        return PUBLIC_PATHS.some((p) => pathname === p || pathname.endsWith(p));
    }

    async function guardPage(options) {
        options = options || {};
        const redirectTo = options.redirectTo || "/student-4/signin.html";
        const mainSelector = options.mainSelector || "main";

        if (isPublicPath(window.location.pathname)) {
            return true;
        }

        const main = document.querySelector(mainSelector);
        if (main) main.style.display = "none";

        const user = await global.NextStopSession.verifySession();
        if (!user) {
            window.location.replace(redirectTo);
            return false;
        }

        if (main) main.style.display = "";
        return true;
    }

    global.NextStopAuthGuard = { guardPage };
})(window);
