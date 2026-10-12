(() => {
    "use strict";

    const tg = window.Telegram?.WebApp;
    const pageSize = 30;
    const initialView = window.location.pathname.replace(/\/+$/, "") === "/my" ? "my" : "catalog";
    const state = {groups: [], filtered: [], visible: pageSize, selected: new Set(), toastTimer: null};
    const $ = selector => document.querySelector(selector);
    const $$ = selector => [...document.querySelectorAll(selector)];

    const elements = {
        search: $("#search"), filters: $("#filters"), filtersToggle: $("#filters-toggle"),
        filterCount: $("#filter-count"), institute: $("#institute"), form: $("#form"),
        type: $("#type"), course: $("#course"), reset: $("#reset"),
        catalogLoading: $("#catalog-loading"), catalogEmpty: $("#catalog-empty"),
        catalogError: $("#catalog-error"), list: $("#groups"), count: $("#result-count"),
        showMore: $("#show-more"), template: $("#group-template"), toast: $("#toast"),
        myAuth: $("#my-auth"), myLoading: $("#my-loading"), myEmpty: $("#my-empty"),
        myGroups: $("#my-groups"), overlay: $("#schedule-overlay"),
        scheduleTitle: $("#schedule-title"), scheduleCaption: $("#schedule-caption"),
        scheduleMeta: $("#schedule-meta"), scheduleDays: $("#schedule-days")
    };

    function setupTelegram() {
        if(!tg) return;
        tg.ready();
        tg.expand();
        tg.setHeaderColor("#16223a");
        tg.setBackgroundColor("#f3f5f9");
    }

    async function api(path, options = {}) {
        const response = await fetch(`/api/${path}`, {
            headers: {"Accept": "application/json", ...(options.body ? {"Content-Type": "application/json"} : {})},
            ...options
        });
        let data;
        try { data = await response.json(); }
        catch { data = {message: `Ошибка сервера (${response.status})`}; }
        if(!response.ok) throw new Error(data.message || `Ошибка сервера (${response.status})`);
        return data;
    }

    function authBody(extra = {}) {
        if(!tg?.initData) throw new Error("Откройте приложение через Telegram-бота");
        return JSON.stringify({auth: tg.initData, ...extra});
    }

    function node(tag, className, text) {
        const item = document.createElement(tag);
        if(className) item.className = className;
        if(text !== undefined) item.textContent = text;
        return item;
    }

    function showView(name) {
        $$("[data-view]").forEach(view => view.classList.toggle("is-active", view.dataset.view === name));
        $$(".nav-item").forEach(link => link.classList.toggle("is-active", link.dataset.viewLink === name));
        window.scrollTo({top: 0, behavior: "smooth"});
        if(name === "my") loadMyGroups();
        if(name === "about") loadStats();
    }

    async function loadGroups() {
        elements.catalogLoading.hidden = false;
        elements.catalogError.hidden = true;
        try {
            const data = await api("groups");
            state.groups = data.groups || [];
            fillFilters();
            applyFilters();
            if(tg?.initData && initialView !== "my") loadMyGroups(false);
        } catch(error) {
            elements.catalogError.hidden = false;
            elements.count.textContent = "Ошибка загрузки";
            showToast(error.message, true);
        } finally {
            elements.catalogLoading.hidden = true;
        }
    }

    function uniqueValues(key) {
        return [...new Set(state.groups.map(group => String(group[key])).filter(Boolean))]
            .sort((a, b) => a.localeCompare(b, "ru", {numeric: true}));
    }

    function fillSelect(select, values, suffix = "") {
        const first = select.options[0];
        select.replaceChildren(first);
        values.forEach(value => {
            const option = node("option", "", `${value}${suffix}`);
            option.value = value;
            select.append(option);
        });
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
        const selected = {institute: elements.institute.value, form: elements.form.value, type: elements.type.value, course: elements.course.value};
        state.filtered = state.groups.filter(group => {
            const searchable = normalize(`${group.name} ${group.institute} ${group.form} ${group.type}`);
            return (!query || searchable.includes(query))
                && Object.entries(selected).every(([key, value]) => !value || String(group[key]) === value);
        });
        state.visible = pageSize;
        const activeCount = Object.values(selected).filter(Boolean).length;
        elements.filterCount.textContent = activeCount;
        elements.filterCount.hidden = !activeCount;
        renderCatalog();
    }

    function renderCatalog() {
        const fragment = document.createDocumentFragment();
        state.filtered.slice(0, state.visible).forEach(group => fragment.append(createGroupCard(group)));
        elements.list.replaceChildren(fragment);
        elements.catalogEmpty.hidden = !!state.filtered.length;
        elements.count.textContent = formatGroupCount(state.filtered.length);
        elements.showMore.hidden = state.visible >= state.filtered.length;
    }

    function createGroupCard(group) {
        const card = elements.template.content.firstElementChild.cloneNode(true);
        card.querySelector(".group-card__name").textContent = group.name;
        card.querySelector(".group-card__course").textContent = `${group.course} курс`;
        card.querySelector(".group-card__institute").textContent = group.institute;
        card.querySelector(".group-card__form").textContent = group.form;
        card.querySelector(".group-card__type").textContent = group.type;
        card.querySelector(".group-card__schedule").addEventListener("click", () => openGroupSchedule(group.id));
        const select = card.querySelector(".group-card__select");
        if(state.selected.has(Number(group.id))) {
            select.textContent = "Добавлена ✓";
            select.classList.add("is-done");
            select.disabled = true;
        } else {
            select.addEventListener("click", () => selectGroup(group, select));
        }
        return card;
    }

    async function selectGroup(group, button) {
        try {
            button.disabled = true;
            button.textContent = "Добавляем…";
            const data = await api("subscribe", {method: "POST", body: authBody({id: Number(group.id)})});
            state.selected.add(Number(group.id));
            button.textContent = "Добавлена ✓";
            button.classList.add("is-done");
            tg?.HapticFeedback?.notificationOccurred("success");
            showToast(data.message);
        } catch(error) {
            button.disabled = false;
            button.textContent = "Добавить";
            tg?.HapticFeedback?.notificationOccurred("error");
            showToast(error.message, true);
        }
    }

    async function loadMyGroups(showLoader = true) {
        if(!tg?.initData) {
            elements.myAuth.hidden = false;
            elements.myEmpty.hidden = true;
            return;
        }
        elements.myAuth.hidden = true;
        if(showLoader) elements.myLoading.hidden = false;
        try {
            const data = await api("me/groups", {method: "POST", body: authBody()});
            const groups = data.groups || [];
            state.selected = new Set(groups.map(group => Number(group.id)));
            renderMyGroups(groups);
            if(state.groups.length) renderCatalog();
        } catch(error) {
            showToast(error.message, true);
        } finally {
            elements.myLoading.hidden = true;
        }
    }

    function renderMyGroups(groups) {
        elements.myEmpty.hidden = !!groups.length;
        const fragment = document.createDocumentFragment();
        groups.forEach(group => {
            const card = createGroupCard(group);
            const actions = card.querySelector(".card-actions");
            card.querySelector(".group-card__select").remove();
            const notifications = node("button", `button ${group.subscribe ? "button--success" : "button--secondary"}`, group.subscribe ? "🔔 Рассылка включена" : "🔕 Включить рассылку");
            notifications.addEventListener("click", () => toggleNotifications(group, notifications));
            const remove = node("button", "button button--danger", "Удалить");
            remove.addEventListener("click", () => removeGroup(group, card));
            actions.append(notifications, remove);
            fragment.append(card);
        });
        elements.myGroups.replaceChildren(fragment);
    }

    async function toggleNotifications(group, button) {
        button.disabled = true;
        try {
            const data = await api("group/toggle-notifications", {method: "POST", body: authBody({id: Number(group.id)})});
            group.subscribe = data.subscribe;
            button.textContent = data.subscribe ? "🔔 Рассылка включена" : "🔕 Включить рассылку";
            button.className = `button ${data.subscribe ? "button--success" : "button--secondary"}`;
            showToast(data.message);
        } catch(error) { showToast(error.message, true); }
        finally { button.disabled = false; }
    }

    async function removeGroup(group, card) {
        if(!window.confirm(`Удалить группу ${group.name} из ваших групп?`)) return;
        try {
            const data = await api("group/remove", {method: "POST", body: authBody({id: Number(group.id)})});
            state.selected.delete(Number(group.id));
            card.remove();
            if(!elements.myGroups.children.length) elements.myEmpty.hidden = false;
            renderCatalog();
            showToast(data.message);
        } catch(error) { showToast(error.message, true); }
    }

    async function openGroupSchedule(groupId) {
        openScheduleLoading("Расписание группы");
        try {
            const data = await api(`group/${encodeURIComponent(groupId)}/schedule`);
            elements.scheduleCaption.textContent = "Учебная группа";
            elements.scheduleTitle.textContent = data.group.name;
            elements.scheduleMeta.textContent = `${data.group.form} · ${data.group.type} · ${data.group.course} курс`;
            renderSchedule(data.days);
        } catch(error) { renderScheduleError(error.message); }
    }

    async function searchEntity(kind) {
        const input = $(`#${kind}-search`);
        const output = $(`#${kind}-results`);
        const query = input.value.trim();
        if(query.length < 2) return showToast("Введите не менее двух символов", true);
        output.replaceChildren(node("div", "state state--compact", "Ищем…"));
        try {
            const data = await api(`entities?kind=${encodeURIComponent(kind)}&q=${encodeURIComponent(query)}`);
            if(!data.entities.length) {
                output.replaceChildren(node("div", "notice", "Ничего не найдено. Попробуйте изменить запрос."));
                return;
            }
            const fragment = document.createDocumentFragment();
            data.entities.forEach(entity => {
                const button = node("button", "entity-item");
                button.append(node("strong", "", entity.value), node("span", "", `Ближайшее занятие: ${formatDate(entity.next_date)}`));
                button.addEventListener("click", () => openEntitySchedule(kind, entity));
                fragment.append(button);
            });
            output.replaceChildren(fragment);
        } catch(error) {
            output.replaceChildren(node("div", "notice notice--error", error.message));
        }
    }

    async function openEntitySchedule(kind, entity) {
        openScheduleLoading(kind === "room" ? "Расписание аудитории" : "Расписание преподавателя");
        try {
            const data = await api(`entity/${kind}/${encodeURIComponent(entity.token)}/schedule`);
            elements.scheduleCaption.textContent = kind === "room" ? "Аудитория" : "Преподаватель";
            elements.scheduleTitle.textContent = data.value;
            elements.scheduleMeta.textContent = "Ближайшие занятия";
            renderSchedule(data.days, true);
        } catch(error) { renderScheduleError(error.message); }
    }

    function openScheduleLoading(title) {
        elements.scheduleCaption.textContent = "";
        elements.scheduleTitle.textContent = title;
        elements.scheduleMeta.textContent = "Загрузка…";
        elements.scheduleDays.replaceChildren(node("div", "state", "Получаем расписание"));
        elements.overlay.hidden = false;
        document.body.classList.add("no-scroll");
    }

    function closeSchedule() {
        elements.overlay.hidden = true;
        document.body.classList.remove("no-scroll");
    }

    function renderSchedule(days, showGroup = false) {
        if(!days.length) {
            elements.scheduleDays.replaceChildren(node("div", "state", "Ближайших занятий нет"));
            return;
        }
        const fragment = document.createDocumentFragment();
        days.forEach((day, index) => {
            const details = node("details", "schedule-day");
            if(index === 0) details.open = true;
            const summary = node("summary");
            const dateBlock = node("span", "day-date");
            dateBlock.append(node("strong", "", formatDate(day.date)), node("small", "", day.weekday));
            const summaryInfo = node("span", "day-summary");
            if(day.weather) summaryInfo.append(node("small", "", `${day.weather.weather} ${day.weather.temp}°C`));
            summaryInfo.append(node("span", "lesson-count", `${day.lessons.length} ${lessonWord(day.lessons.length)}`));
            summary.append(dateBlock, summaryInfo);
            details.append(summary);
            const lessons = node("div", "lessons");
            day.lessons.forEach(lesson => {
                const item = node("article", "lesson");
                const time = node("div", "lesson__time");
                time.append(node("strong", "", lesson.start), node("span", "", lesson.end));
                const content = node("div", "lesson__content");
                content.append(node("h4", "", lesson.name), node("p", "lesson__type", `${lesson.number} пара · ${lesson.type || "Тип не указан"}`));
                const tags = node("div", "lesson__tags");
                if(showGroup && lesson.group) tags.append(node("span", "", `🎓 ${lesson.group}`));
                if(lesson.room && lesson.room_token) {
                    const room = node("button", "lesson-link", `🚪 ${lesson.room}`);
                    room.type = "button";
                    room.addEventListener("click", () => openEntitySchedule("room", {value: lesson.room, token: lesson.room_token}));
                    tags.append(room);
                }
                if(lesson.teacher && lesson.teacher !== "Нет данных" && lesson.teacher_token) {
                    const teacher = node("button", "lesson-link", `👨‍🏫 ${lesson.teacher}`);
                    teacher.type = "button";
                    teacher.addEventListener("click", () => openEntitySchedule("teacher", {value: lesson.teacher, token: lesson.teacher_token}));
                    tags.append(teacher);
                }
                content.append(tags);
                item.append(time, content);
                lessons.append(item);
            });
            details.append(lessons);
            fragment.append(details);
        });
        elements.scheduleDays.replaceChildren(fragment);
    }

    function renderScheduleError(message) {
        elements.scheduleMeta.textContent = "";
        elements.scheduleDays.replaceChildren(node("div", "notice notice--error", message));
    }

    async function loadStats() {
        const output = $("#stats");
        if(output.children.length) return;
        try {
            const data = await api("stats");
            const values = [[data.groups, "групп"], [data.lessons, "будущих занятий"], [data.users, "пользователей"]];
            values.forEach(([value, label]) => {
                const item = node("div", "stat");
                item.append(node("strong", "", value.toLocaleString("ru")), node("span", "", label));
                output.append(item);
            });
        } catch(error) { output.replaceChildren(node("div", "notice notice--error", error.message)); }
    }

    function formatDate(value) {
        return new Intl.DateTimeFormat("ru-RU", {day: "2-digit", month: "long"}).format(new Date(`${value}T12:00:00`));
    }

    function lessonWord(count) {
        if(count % 10 === 1 && count % 100 !== 11) return "пара";
        if([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100)) return "пары";
        return "пар";
    }

    function formatGroupCount(count) {
        const word = count % 10 === 1 && count % 100 !== 11 ? "группа" : ([2,3,4].includes(count % 10) && ![12,13,14].includes(count % 100) ? "группы" : "групп");
        return `${count} ${word}`;
    }

    function showToast(message, isError = false) {
        clearTimeout(state.toastTimer);
        elements.toast.textContent = message;
        elements.toast.classList.toggle("is-error", isError);
        elements.toast.classList.add("is-visible");
        state.toastTimer = setTimeout(() => elements.toast.classList.remove("is-visible"), 3500);
    }

    let searchTimer;
    elements.search.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(applyFilters, 120); });
    [elements.institute, elements.form, elements.type, elements.course].forEach(select => select.addEventListener("change", applyFilters));
    elements.filtersToggle.addEventListener("click", () => {
        const open = elements.filters.classList.toggle("is-open");
        elements.filtersToggle.setAttribute("aria-expanded", String(open));
    });
    elements.reset.addEventListener("click", () => {
        elements.search.value = "";
        [elements.institute, elements.form, elements.type, elements.course].forEach(select => select.value = "");
        applyFilters();
    });
    elements.showMore.addEventListener("click", () => { state.visible += pageSize; renderCatalog(); });
    $("#retry").addEventListener("click", loadGroups);
    $$('[data-view-link]').forEach(link => link.addEventListener("click", () => showView(link.dataset.viewLink)));
    $$('[data-entity-search]').forEach(button => button.addEventListener("click", () => searchEntity(button.dataset.entitySearch)));
    [$("#room-search"), $("#teacher-search")].forEach(input => input.addEventListener("keydown", event => {
        if(event.key === "Enter") searchEntity(input.id.startsWith("room") ? "room" : "teacher");
    }));
    $("#schedule-close").addEventListener("click", closeSchedule);
    elements.overlay.addEventListener("click", event => { if(event.target === elements.overlay) closeSchedule(); });
    document.addEventListener("keydown", event => { if(event.key === "Escape" && !elements.overlay.hidden) closeSchedule(); });

    setupTelegram();
    if(initialView !== "catalog") showView(initialView);
    loadGroups();
})();
