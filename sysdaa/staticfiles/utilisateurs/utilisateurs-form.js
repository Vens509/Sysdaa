(function () {
    "use strict";

    function normalize(value) {
        return String(value || "").trim().toLowerCase();
    }

    function parseJSON(value, fallback) {
        try {
            return JSON.parse(value || "");
        } catch (e) {
            return fallback;
        }
    }

    function getSelectedLabel(select) {
        if (!select) return "";
        const opt = select.options[select.selectedIndex];
        return opt ? opt.text : "";
    }

    function findOptionByValue(select, value) {
        if (!select) return null;
        return Array.from(select.options).find(function (option) {
            return String(option.value || "") === String(value || "");
        }) || null;
    }

    function setLockedSelect(select, locked) {
        if (!select) return;
        if (locked) {
            select.setAttribute("disabled", "disabled");
            select.classList.add("bg-light");
        } else {
            select.removeAttribute("disabled");
            select.classList.remove("bg-light");
        }
    }

    function resetDirectionOptions(directionSelect) {
        if (!directionSelect) return;
        Array.from(directionSelect.options).forEach(function (option) {
            option.disabled = false;
        });
    }

    function updateFormLogic() {
        const roleSelect = document.querySelector('[data-role-select="true"]');
        const directionSelect = document.querySelector('[data-direction-select="true"]');
        const hiddenDirectorInput = document.querySelector('input[name="directeur_superviseur"]');
        const directionHelp = document.getElementById("direction-affectee-help");

        if (!roleSelect || !directionSelect) return;

        const roleLabel = normalize(getSelectedLabel(roleSelect));
        const lockedRoles = [
            "gestionnaire des ressources matérielles",
            "directeur daa"
        ];
        const assistantRole = "assistant de directeur";

        const daaId = String(directionSelect.getAttribute("data-direction-daa-id") || "");
        const blocked = parseJSON(
            directionSelect.getAttribute("data-assistant-blocked-directions"),
            []
        ).map(String);
        const directorMap = parseJSON(
            directionSelect.getAttribute("data-assistant-director-map"),
            {}
        );

        resetDirectionOptions(directionSelect);

        if (lockedRoles.includes(roleLabel)) {
            if (daaId) {
                directionSelect.value = daaId;
            }
            setLockedSelect(directionSelect, true);

            if (hiddenDirectorInput) {
                hiddenDirectorInput.value = "";
            }
            return;
        }

        if (roleLabel === assistantRole) {
            setLockedSelect(directionSelect, false);

            Array.from(directionSelect.options).forEach(function (opt) {
                if (!opt.value) return;
                if (blocked.includes(String(opt.value)) && String(opt.value) !== String(directionSelect.value || "")) {
                    opt.disabled = true;
                }
            });

            const selectedDir = String(directionSelect.value || "");
            const directorData = directorMap[selectedDir];

            if (hiddenDirectorInput) {
                hiddenDirectorInput.value = directorData && directorData.id ? directorData.id : "";
            }

            if (directionHelp) {
                directionHelp.textContent = "Choisissez une direction disponible. Le directeur sera rattaché automatiquement si un directeur actif existe.";
            }
            return;
        }

        setLockedSelect(directionSelect, false);

        if (hiddenDirectorInput) {
            hiddenDirectorInput.value = "";
        }

        if (directionHelp) {
            directionHelp.textContent = "Sélection manuelle autorisée pour ce rôle.";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const roleSelect = document.querySelector('[data-role-select="true"]');
        const directionSelect = document.querySelector('[data-direction-select="true"]');

        if (!roleSelect || !directionSelect) return;

        updateFormLogic();
        roleSelect.addEventListener("change", updateFormLogic);
        directionSelect.addEventListener("change", updateFormLogic);
    });
})();