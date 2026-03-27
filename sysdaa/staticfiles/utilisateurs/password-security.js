(function () {
    "use strict";

    const CONFIG = {
        password1Id: "id_password1",
        password2Id: "id_password2",
        messageDuration: 2600,
    };

    function createToastContainer() {
        let container = document.getElementById("sys-toast-container");

        if (!container) {
            container = document.createElement("div");
            container.id = "sys-toast-container";
            document.body.appendChild(container);
        }

        return container;
    }

    function showToast(message, type = "warning") {
        const container = createToastContainer();

        const toast = document.createElement("div");
        toast.textContent = message;
        toast.className = "sys-security-toast";

        if (type === "error") {
            toast.classList.add("sys-security-toast--error");
        } else if (type === "success") {
            toast.classList.add("sys-security-toast--success");
        } else {
            toast.classList.add("sys-security-toast--warning");
        }

        container.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";
        });

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-8px)";
            setTimeout(() => {
                toast.remove();
            }, 250);
        }, CONFIG.messageDuration);
    }

    function ensureHelperUI(passwordField, confirmField) {
        let wrapper = document.getElementById("sys-password-helper");

        if (wrapper) {
            return {
                strengthText: document.getElementById("sys-password-strength-text"),
                strengthBar: document.getElementById("sys-password-strength-bar"),
                matchText: document.getElementById("sys-password-match-text"),
            };
        }

        wrapper = document.createElement("div");
        wrapper.id = "sys-password-helper";

        const strengthLabel = document.createElement("div");
        strengthLabel.id = "sys-password-strength-text";
        strengthLabel.textContent = "Force du mot de passe : en attente";

        const barOuter = document.createElement("div");
        barOuter.id = "sys-password-strength-bar-wrap";

        const barInner = document.createElement("div");
        barInner.id = "sys-password-strength-bar";

        barOuter.appendChild(barInner);

        const matchText = document.createElement("div");
        matchText.id = "sys-password-match-text";
        matchText.textContent = "Confirmation : en attente";

        wrapper.appendChild(strengthLabel);
        wrapper.appendChild(barOuter);
        wrapper.appendChild(matchText);

        const targetContainer =
            (confirmField && confirmField.parentElement) ||
            (passwordField && passwordField.parentElement);

        if (targetContainer) {
            targetContainer.appendChild(wrapper);
        }

        return {
            strengthText: strengthLabel,
            strengthBar: barInner,
            matchText: matchText,
        };
    }

    function blockRestrictedActions(field) {
        if (!field || field.dataset.passwordSecurityBound === "true") return;

        field.dataset.passwordSecurityBound = "true";

        const blockedEvents = ["paste", "copy", "cut", "drop"];

        blockedEvents.forEach((eventName) => {
            field.addEventListener(eventName, function (e) {
                e.preventDefault();

                let message = "Action non autorisée sur ce champ.";

                if (eventName === "paste") {
                    message = "Le collage du mot de passe est désactivé. Veuillez le saisir manuellement.";
                } else if (eventName === "copy") {
                    message = "La copie du mot de passe est désactivée.";
                } else if (eventName === "cut") {
                    message = "La coupure du mot de passe est désactivée.";
                } else if (eventName === "drop") {
                    message = "Le glisser-déposer est désactivé sur ce champ.";
                }

                showToast(message, "warning");
            });
        });

        field.addEventListener("keydown", function (e) {
            const key = (e.key || "").toLowerCase();
            const combo = e.ctrlKey || e.metaKey;

            if (!combo) return;

            if (key === "v" || key === "c" || key === "x") {
                e.preventDefault();

                let message = "Raccourci non autorisé.";

                if (key === "v") {
                    message = "Ctrl+V est désactivé pour les mots de passe.";
                } else if (key === "c") {
                    message = "Ctrl+C est désactivé pour les mots de passe.";
                } else if (key === "x") {
                    message = "Ctrl+X est désactivé pour les mots de passe.";
                }

                showToast(message, "warning");
            }
        });
    }

    function scorePassword(password) {
        let score = 0;

        if (!password) {
            return 0;
        }

        if (password.length >= 8) score += 20;
        if (password.length >= 12) score += 15;
        if (/[a-z]/.test(password)) score += 15;
        if (/[A-Z]/.test(password)) score += 15;
        if (/[0-9]/.test(password)) score += 15;
        if (/[^A-Za-z0-9]/.test(password)) score += 20;

        return Math.min(score, 100);
    }

    function getStrengthMeta(score) {
        if (score === 0) {
            return {
                label: "Force du mot de passe : en attente",
                color: "#cbd5e1",
                width: "0%",
            };
        }

        if (score < 35) {
            return {
                label: "Force du mot de passe : faible",
                color: "#ef4444",
                width: score + "%",
            };
        }

        if (score < 65) {
            return {
                label: "Force du mot de passe : moyenne",
                color: "#f59e0b",
                width: score + "%",
            };
        }

        if (score < 85) {
            return {
                label: "Force du mot de passe : bonne",
                color: "#3b82f6",
                width: score + "%",
            };
        }

        return {
            label: "Force du mot de passe : forte",
            color: "#10b981",
            width: score + "%",
        };
    }

    function updateStrength(passwordField, ui) {
        if (!passwordField || !ui) return;

        const score = scorePassword(passwordField.value);
        const meta = getStrengthMeta(score);

        ui.strengthText.textContent = meta.label;
        ui.strengthText.style.color = meta.color;
        ui.strengthBar.style.width = meta.width;
        ui.strengthBar.style.background = meta.color;
    }

    function updateMatch(passwordField, confirmField, ui) {
        if (!passwordField || !confirmField || !ui) return;

        const password = passwordField.value;
        const confirmPassword = confirmField.value;

        passwordField.classList.remove("sys-pwd-ok", "sys-pwd-error");
        confirmField.classList.remove("sys-pwd-ok", "sys-pwd-error");

        if (!confirmPassword) {
            ui.matchText.textContent = "Confirmation : en attente";
            ui.matchText.style.color = "#64748b";
            confirmField.setCustomValidity("");
            return;
        }

        if (password === confirmPassword) {
            ui.matchText.textContent = "Confirmation : les mots de passe correspondent";
            ui.matchText.style.color = "#059669";
            passwordField.classList.add("sys-pwd-ok");
            confirmField.classList.add("sys-pwd-ok");
            confirmField.setCustomValidity("");
            return;
        }

        ui.matchText.textContent = "Confirmation : les mots de passe ne correspondent pas";
        ui.matchText.style.color = "#dc2626";
        confirmField.classList.add("sys-pwd-error");
        confirmField.setCustomValidity("Les mots de passe ne correspondent pas.");
    }

    function blockAutofillHints(field) {
        if (!field) return;

        field.setAttribute("autocomplete", "new-password");
        field.setAttribute("autocorrect", "off");
        field.setAttribute("autocapitalize", "none");
        field.setAttribute("spellcheck", "false");
    }

    function resolvePasswordFields() {
        const password1 =
            document.getElementById(CONFIG.password1Id) ||
            document.querySelector('input[type="password"][name="password1"]') ||
            document.querySelector('input[type="password"][data-password-protected="true"]');

        const password2 =
            document.getElementById(CONFIG.password2Id) ||
            document.querySelector('input[type="password"][name="password2"]') ||
            document.querySelectorAll('input[type="password"][data-password-protected="true"]')[1] ||
            null;

        return { password1, password2 };
    }

    document.addEventListener("DOMContentLoaded", function () {
        const protectedFields = document.querySelectorAll(
            'input[type="password"], input.password-protected, input[data-password-protected="true"]'
        );

        protectedFields.forEach(function (field) {
            blockAutofillHints(field);
            blockRestrictedActions(field);
        });

        const { password1, password2 } = resolvePasswordFields();

        if (!password1 || !password2) {
            return;
        }

        const ui = ensureHelperUI(password1, password2);

        updateStrength(password1, ui);
        updateMatch(password1, password2, ui);

        password1.addEventListener("input", function () {
            updateStrength(password1, ui);
            updateMatch(password1, password2, ui);
        });

        password2.addEventListener("input", function () {
            updateMatch(password1, password2, ui);
        });

        if (password1.form) {
            password1.form.addEventListener("submit", function () {
                updateMatch(password1, password2, ui);
            });
        }
    });
})();