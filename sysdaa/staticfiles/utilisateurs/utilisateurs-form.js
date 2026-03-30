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

    function disableOptionsByIds(directionSelect, ids, keepCurrentValue) {
        if (!directionSelect) return;

        const selectedValue = String(directionSelect.value || "");
        const blockedIds = (ids || []).map(String);

        Array.from(directionSelect.options).forEach(function (opt) {
            if (!opt.value) return;

            const optionValue = String(opt.value || "");
            const isBlocked = blockedIds.includes(optionValue);
            const isCurrent = optionValue === selectedValue;

            if (isBlocked && !(keepCurrentValue && isCurrent)) {
                opt.disabled = true;
            }
        });
    }

    function updateFormLogic() {
        const roleSelect = document.querySelector('[data-role-select="true"]');
        const directionSelect = document.querySelector('[data-direction-select="true"]');
        const hiddenDirectorInput = document.querySelector('input[name="directeur_superviseur"]');
        const directionHelp = document.getElementById("direction-affectee-help");

        if (!roleSelect || !directionSelect) return;

        const roleLabel = normalize(getSelectedLabel(roleSelect));

        const lockedRoles = parseJSON(
            roleSelect.getAttribute("data-role-locked-daa"),
            []
        ).map(normalize);

        const assistantRole = normalize(
            roleSelect.getAttribute("data-role-assistant") || "Assistant de directeur"
        );

        const directorRole = normalize(
            roleSelect.getAttribute("data-role-director-direction") || "Directeur de direction"
        );

        const daaId = String(directionSelect.getAttribute("data-direction-daa-id") || "");

        const assistantBlocked = parseJSON(
            directionSelect.getAttribute("data-assistant-blocked-directions"),
            []
        ).map(String);

        const directorBlocked = parseJSON(
            directionSelect.getAttribute("data-director-blocked-directions"),
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

            if (directionHelp) {
                directionHelp.textContent = "Cette direction est imposée pour ce rôle.";
            }
            return;
        }

        setLockedSelect(directionSelect, false);

        if (roleLabel === directorRole) {
            disableOptionsByIds(directionSelect, directorBlocked, true);

            if (hiddenDirectorInput) {
                hiddenDirectorInput.value = "";
            }

            if (directionHelp) {
                directionHelp.textContent = "Les directions ayant déjà un directeur actif sont grisées et inaccessibles.";
            }
            return;
        }

        if (roleLabel === assistantRole) {
            disableOptionsByIds(directionSelect, assistantBlocked, true);

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