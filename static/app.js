(() => {
    "use strict";

    const tg = window.Telegram?.WebApp;
    const pageSize = 30;
    let groups = [];
    let filteredGroups = [];
    let visibleCount = pageSize;
    let toastTimer;

    const elements = {
        search: document.querySelector("#search"),
        filters: document.querySelector("#filters"),
        filtersToggle: document.querySelector("#filters-toggle"),
        filterCount: document.querySelector("#filter-count"),
        institute: document.querySelector("#institute"),
        form: document.querySelector("#form"),
        type: document.querySelector("#type"),
        course: document.querySelector("#course"),
        reset: document.querySelector("#reset"),
        loading: document.querySelector("#loading"),
        empty: document.querySelector("#empty"),
        error: document.querySelector("#error"),
        retry: document.querySelector("#retry"),
        list: document.querySelector("#groups"),
        count: document.querySelector("#result-count"),
        showMore: document.querySelector("#show-more"),
        template: document.querySelector("#group-template"),
        toast: document.querySelector("#toast")
    };

    function setupTelegram() {
        if(!tg) return;
        tg.ready();
        tg.expand();
        tg.setHeaderColor("#16223a");
        tg.setBackgroundColor("#f3f5f9");
    }

    function endpoint(path) {
        return `/api/${path}`;
    }

    async function loadGroups() {
        elements.loading.hidden = false;
        elements.error.hidden = true;
        elements.empty.hidden = true;
        elements.list.replaceChildren();
        try {
            let response = await fetch(endpoint("groups"), {headers: {"Accept": "application/json"}});
            if(response.status === 404) response = await fetch("/groups", {headers: {"Accept": "application/json"}});
            if(!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            groups = data.groups ?? [];
            fillFilters();
            applyFilters();
        } catch(error) {
            console.error(error);
            elements.error.hidden = false;
            elements.count.textContent = "Ошибка загрузки";
        } finally {
            elements.loading.hidden = true;
        }
    }

    function uniqueValues(key) {
        return [...new Set(groups.map(group => String(group[key])).filter(Boolean))]
            .sort((left, right) => left.localeCompare(right, "ru", {numeric: true}));
    }

    function fillSelect(select, values, suffix = "") {
        const current = select.value;
        select.replaceChildren(select.options[0]);
        values.forEach(value => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = `${value}${suffix}`;
            select.append(option);
        });
        select.value = current;
    }

    function fillFilters() {
        fillSelect(elements.institute, uniqueValues("institute"));
        fillSelect(elements.form, uniqueValues("form"));
        fillSelect(elements.type, uniqueValues("type"));
        fillSelect(elements.course, uniqueValues("course"), " курс");
    }

    function normalize(value) {
        return String(value).toLocaleLowerCase("ru").replaceAll("ё", "е").trim();
    }

    function applyFilters() {
        const query = normalize(elements.search.value);
        const selected = {
            institute: elements.institute.value,
            form: elements.form.value,
            type: elements.type.value,
            course: elements.course.value
        };
        filteredGroups = groups.filter(group => {
            const searchable = normalize(`${group.name} ${group.institute} ${group.form} ${group.type}`);
            return (!query || searchable.includes(query))
                && Object.entries(selected).every(([key, value]) => !value || String(group[key]) === value);
        });
        visibleCount = pageSize;
        const activeCount = Object.values(selected).filter(Boolean).length;
        elements.filterCount.textContent = activeCount;
        elements.filterCount.hidden = activeCount === 0;
        renderGroups();
    }

    function renderGroups() {
        const fragment = document.createDocumentFragment();
        filteredGroups.slice(0, visibleCount).forEach(group => fragment.append(createGroupCard(group)));
        elements.list.replaceChildren(fragment);
        elements.empty.hidden = filteredGroups.length !== 0;
        elements.count.textContent = formatGroupCount(filteredGroups.length);
        elements.showMore.hidden = visibleCount >= filteredGroups.length;
    }

    function createGroupCard(group) {
        const card = elements.template.content.firstElementChild.cloneNode(true);
        card.querySelector(".group-card__name").textContent = group.name;
        card.querySelector(".group-card__course").textContent = `${group.course} курс`;
        card.querySelector(".group-card__institute").textContent = group.institute;
        card.querySelector(".group-card__form").textContent = group.form;
        card.querySelector(".group-card__type").textContent = group.type;
        const button = card.querySelector(".group-card__select");
        button.addEventListener("click", () => selectGroup(group, button));
        return card;
    }

    async function selectGroup(group, button) {
        if(!tg?.initData) {
            showToast("Откройте эту страницу кнопкой в Telegram-боте", true);
            return;
        }
        button.disabled = true;
        button.textContent = "Добавляем…";
        try {
            let response = await fetch(endpoint("subscribe"), {
                method: "POST",
                headers: {"Content-Type": "application/json", "Accept": "application/json"},
                body: JSON.stringify({id: Number(group.id), auth: tg.initData})
            });
            if(response.status === 404) {
                response = await fetch("/subscribe", {
                    method: "POST",
                    headers: {"Content-Type": "application/json", "Accept": "application/json"},
                    body: JSON.stringify({id: Number(group.id), auth: tg.initData})
                });
            }
            const data = await response.json();
            if(!response.ok || data.status !== "success") throw new Error(data.message || "Не удалось добавить группу");
            button.textContent = "Добавлена ✓";
            button.classList.add("is-done");
            tg.HapticFeedback?.notificationOccurred("success");
            showToast(data.message);
        } catch(error) {
            button.disabled = false;
            button.textContent = "Выбрать";
            tg.HapticFeedback?.notificationOccurred("error");
            showToast(error.message || "Произошла ошибка", true);
        }
    }

    function formatGroupCount(count) {
        const lastTwo = count % 100;
        const last = count % 10;
        let word = "групп";
        if(lastTwo < 11 || lastTwo > 14) {
            if(last === 1) word = "группа";
            else if(last >= 2 && last <= 4) word = "группы";
        }
        return `${count} ${word}`;
    }

    function showToast(message, isError = false) {
        clearTimeout(toastTimer);
        elements.toast.textContent = message;
        elements.toast.classList.toggle("is-error", isError);
        elements.toast.classList.add("is-visible");
        toastTimer = setTimeout(() => elements.toast.classList.remove("is-visible"), 3500);
    }

    let searchTimer;
    elements.search.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(applyFilters, 120);
    });
    [elements.institute, elements.form, elements.type, elements.course]
        .forEach(select => select.addEventListener("change", applyFilters));
    elements.filtersToggle.addEventListener("click", () => {
        const isOpen = elements.filters.classList.toggle("is-open");
        elements.filtersToggle.setAttribute("aria-expanded", String(isOpen));
    });
    elements.reset.addEventListener("click", () => {
        elements.search.value = "";
        [elements.institute, elements.form, elements.type, elements.course].forEach(select => select.value = "");
        applyFilters();
    });
    elements.showMore.addEventListener("click", () => {
        visibleCount += pageSize;
        renderGroups();
    });
    elements.retry.addEventListener("click", loadGroups);

    setupTelegram();
    loadGroups();
})();
