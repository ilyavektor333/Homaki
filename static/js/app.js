(function () {
    const modal = document.getElementById('catalog-modal');
    const grid = document.getElementById('catalog-grid');
    const empty = document.getElementById('catalog-empty');
    const title = document.getElementById('catalog-title');
    const subtitle = document.getElementById('catalog-subtitle');
    const status = document.getElementById('catalog-status');
    const tierTabs = document.getElementById('catalog-tier-tabs');
    const classModal = document.getElementById('class-modal');

    let activeSlot = null;
    let activeTier = 'T1';
    let requestToken = 0;

    function setStatus(message, error = false) {
        if (!status) return;
        status.textContent = message || '';
        status.classList.toggle('error', error);
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
        activeSlot = null;
        document.body.classList.remove('catalog-modal-open');
    }

    async function loadCatalog() {
        if (!activeSlot || !modal) return;
        const token = ++requestToken;
        grid.innerHTML = '<div class="catalog-loading">ЗАГРУЗКА КАТАЛОГА…</div>';
        empty.hidden = true;
        const url = '/profile/catalog/' + encodeURIComponent(activeSlot) + '?tier=' + encodeURIComponent(activeTier);
        try {
            const response = await fetch(url, { credentials: 'same-origin' });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || 'Не удалось получить каталог.');
            if (token !== requestToken) return;

            title.textContent = data.title || 'Выбор изображения';
            subtitle.textContent = data.class_name
                ? ('Класс: ' + data.class_name + (data.tier ? ' · ' + data.tier : ''))
                : '';
            grid.innerHTML = '';
            if (!data.items || !data.items.length) {
                empty.hidden = false;
                return;
            }

            data.items.forEach((item) => {
                const card = document.createElement('button');
                card.type = 'button';
                card.className = 'catalog-item';
                card.dataset.catalogId = item.id;
                card.innerHTML =
                    '<span class="catalog-image-wrap"><img src="' + escapeHtml(item.image_url) + '" alt=""></span>' +
                    '<span class="catalog-item-name">' + escapeHtml(item.name) + '</span>' +
                    (data.category !== 'character' ? '<span class="catalog-item-tier">' + escapeHtml(item.tier || activeTier) + '</span>' : '');
                card.addEventListener('click', () => selectImage(item.id, item.name));
                grid.appendChild(card);
            });
        } catch (error) {
            if (token !== requestToken) return;
            grid.innerHTML = '<div class="catalog-error">' + escapeHtml(error.message || 'Ошибка загрузки каталога.') + '</div>';
            subtitle.textContent = '';
        }
    }

    function openModal(slot) {
        if (!modal) return;
        activeSlot = slot;
        activeTier = 'T1';
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('catalog-modal-open');
        if (tierTabs) tierTabs.hidden = slot === 'character_card';
        document.querySelectorAll('.catalog-tier').forEach(btn => btn.classList.toggle('active', btn.dataset.tier === activeTier));
        loadCatalog();
    }

    async function selectImage(catalogId, name) {
        if (!activeSlot) return;
        const slot = activeSlot;
        const formData = new FormData();
        formData.append('slot', slot);
        formData.append('catalog_id', String(catalogId));
        setStatus('Выбор изображения…');
        try {
            const response = await fetch('/profile/select-image', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.ok) throw new Error(data.detail || 'Не удалось выбрать изображение.');
            closeModal();
            setStatus('Выбрано: ' + name);
            window.location.reload();
        } catch (error) {
            setStatus(error.message || 'Ошибка выбора.', true);
        }
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        })[char]);
    }

    document.querySelectorAll('.js-catalog-slot').forEach((element) => {
        element.addEventListener('click', (event) => {
            if (event.target.closest('.slot-remove')) return;
            const slot = element.dataset.slot;
            if (slot) openModal(slot);
        });
    });

    document.querySelectorAll('[data-catalog-close]').forEach((element) => {
        element.addEventListener('click', closeModal);
    });

    document.querySelectorAll('.catalog-tier').forEach((button) => {
        button.addEventListener('click', () => {
            activeTier = button.dataset.tier || 'T1';
            document.querySelectorAll('.catalog-tier').forEach(btn => btn.classList.toggle('active', btn === button));
            loadCatalog();
        });
    });

    document.querySelectorAll('[data-remove-slot]').forEach((button) => {
        button.addEventListener('click', async (event) => {
            event.preventDefault();
            event.stopPropagation();
            const slot = button.dataset.removeSlot;
            if (!slot) return;
            if (!window.confirm('Очистить этот слот?')) return;
            const formData = new FormData();
            formData.append('slot', slot);
            setStatus('Очистка слота…');
            try {
                const response = await fetch('/profile/delete-image', { method: 'POST', body: formData, credentials: 'same-origin' });
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.ok) throw new Error(data.detail || 'Не удалось очистить слот.');
                window.location.reload();
            } catch (error) {
                setStatus(error.message || 'Ошибка очистки.', true);
            }
        });
    });

    // Класс игрока.
    const openClassButton = document.getElementById('open-class-modal');
    if (classModal && openClassButton) {
        const closeClass = () => {
            classModal.classList.remove('open');
            classModal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('catalog-modal-open');
        };
        openClassButton.addEventListener('click', () => {
            classModal.classList.add('open');
            classModal.setAttribute('aria-hidden', 'false');
            document.body.classList.add('catalog-modal-open');
        });
        classModal.querySelectorAll('[data-class-close]').forEach(el => el.addEventListener('click', closeClass));
        classModal.querySelectorAll('.class-option').forEach(btn => {
            btn.addEventListener('click', async () => {
                const classKey = btn.dataset.classKey;
                if (!classKey) return;
                const formData = new FormData();
                formData.append('class_key', classKey);
                btn.disabled = true;
                try {
                    const response = await fetch('/profile/set-class', { method: 'POST', body: formData, credentials: 'same-origin' });
                    const data = await response.json().catch(() => ({}));
                    if (!response.ok || !data.ok) throw new Error(data.detail || 'Не удалось сменить класс.');
                    window.location.reload();
                } catch (error) {
                    btn.disabled = false;
                    setStatus(error.message || 'Ошибка смены класса.', true);
                    closeClass();
                }
            });
        });
    }


    // Мини-профиль игрока в составе клана: это уменьшенная копия
    // основного профиля с тем же расположением карточки и экипировки.
    const memberModal = document.getElementById('member-equipment-modal');
    const memberDataNode = document.getElementById('clan-members-data');
    if (memberModal && memberDataNode) {
        let membersData = [];
        try { membersData = JSON.parse(memberDataNode.textContent || '[]'); } catch (_) { membersData = []; }
        const memberTitle = document.getElementById('member-modal-title');
        const memberRole = document.getElementById('member-modal-role');
        const memberClass = document.getElementById('member-modal-class');
        const miniProfile = document.getElementById('member-mini-profile');

        const memberClassMap = {
            vanguard_fighter:'Боец Авангарда', berserk:'Берсерк', destroyer:'Разрушитель',
            night_tracker:'Ночной следопыт', elemental_master:'Мастер стихий', sky_caster:'Небесный заклинатель',
            assassin:'Убийца', deathdealer:'Смертоносец', shooter:'Стрелок', warlord:'Военачальник'
        };
        const memberRoleMap = { chief:{name:'Глава',css:'role-chief'}, officer:{name:'Офицер',css:'role-officer'}, sergeant:{name:'Сержант',css:'role-sergeant'}, fighter:{name:'Боец',css:'role-fighter'} };
        const miniSlots = [
            ['weapon','ОРУЖИЕ','slot-weapon'], ['gloves','ПЕРЧАТКИ','slot-gloves'], ['cloak','ПЛАЩ','slot-cloak'],
            ['earring_1','СЕРЬГА','slot-earring-1'], ['earring_2','СЕРЬГА','slot-earring-2'],
            ['necklace','ОЖЕРЕЛЬЕ','slot-necklace'], ['belt','ПОЯС','slot-belt'],
            ['bracelet_1','БРАСЛЕТ','slot-bracelet-1'], ['bracelet_2','БРАСЛЕТ','slot-bracelet-2'],
            ['ring_1','КОЛЬЦО','slot-ring-1'], ['ring_2','КОЛЬЦО','slot-ring-2'],
            ['totem','ТОТЕМ','slot-totem'], ['seal','ПЕЧАТЬ','slot-seal'],
            ['hat','ШЛЯПА','slot-hat'], ['body','ТЕЛО','slot-body'], ['pants','ШТАНЫ','slot-pants'], ['boots','БОТИНКИ','slot-boots']
        ];

        function memberEquipmentMap(entry) {
            const map = {};
            (entry.equipment || []).forEach(item => { map[item.field] = item; });
            return map;
        }

        function renderMiniProfile(entry) {
            const user = entry.user || {};
            const eq = memberEquipmentMap(entry);
            const characterUrl = user.character_card || '';
            const characterMarkup = characterUrl
                ? '<img src="' + escapeHtml(characterUrl) + '" alt="' + escapeHtml(user.game_nickname || 'Персонаж') + '">'
                : '<div class="member-mini-character-empty">КАРТОЧКА НЕ ВЫБРАНА</div>';

            const equipmentMarkup = miniSlots.map(([field, label, placement]) => {
                const item = eq[field] || {};
                const image = item.image_url
                    ? '<img src="' + escapeHtml(item.image_url) + '" alt="' + escapeHtml(item.name || label) + '">'
                    : '<span class="member-mini-empty-mark">+</span>';
                return '<div class="equipment-slot-wrap ' + placement + '">' +
                    '<div class="equipment-slot member-mini-slot">' + image +
                    '<span class="slot-label">' + escapeHtml(item.image_url ? (item.name || label) : label) + '</span></div></div>';
            }).join('');

            const bottomItems = [
                ['symbol','СИМВОЛ'], ['artifact','АРТЕФАКТ']
            ].map(([field,label]) => {
                const item = eq[field] || {};
                const image = item.image_url
                    ? '<img src="' + escapeHtml(item.image_url) + '" alt="' + escapeHtml(item.name || label) + '">'
                    : '<span class="member-mini-empty-mark">+</span>';
                return '<div class="equipment-slot-wrap equipment-bottom-slot-wrap">' +
                    '<div class="equipment-slot equipment-bottom-slot member-mini-slot">' + image +
                    '<span class="slot-label">' + escapeHtml(item.image_url ? (item.name || label) : label) + '</span></div></div>';
            }).join('');

            miniProfile.innerHTML =
                '<div class="member-mini-stats-bar">' +
                    '<div class="member-mini-stat"><span>⚔</span><b>АТАКА</b><strong>' + escapeHtml(user.attack || 0) + '</strong></div>' +
                    '<div class="member-mini-stat"><span>🛡</span><b>ЗАЩИТА</b><strong>' + escapeHtml(user.defense || 0) + '</strong></div>' +
                    '<div class="member-mini-stat"><span>🎯</span><b>ТОЧНОСТЬ</b><strong>' + escapeHtml(user.accuracy || 0) + '</strong></div>' +
                '</div>' +
                '<div class="member-mini-stage">' +
                    '<section class="member-mini-character-panel">' +
                        '<div class="member-mini-panel-title">КАРТОЧКА ПЕРСОНАЖА</div>' +
                        '<div class="member-mini-character-card">' + characterMarkup + '</div>' +
                    '</section>' +
                    '<section class="member-mini-equipment-panel">' +
                        '<div class="member-mini-panel-title">СНАРЯЖЕНИЕ</div>' +
                        '<div class="equipment-grid member-mini-equipment-grid">' + equipmentMarkup + '</div>' +
                        '<div class="equipment-bottom member-mini-equipment-bottom">' + bottomItems +
                            '<div class="equipment-slot equipment-bottom-slot slot-locked member-mini-slot"><span class="slot-lock">🔒</span><span class="slot-label">ЗАКРЫТ</span></div>' +
                        '</div>' +
                    '</section>' +
                '</div>';
        }

        function closeMemberModal() {
            memberModal.classList.remove('open');
            memberModal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('member-modal-open');
            miniProfile.innerHTML = '';
        }

        function openMemberModal(memberId) {
            const entry = membersData.find(item => String(item.user.id) === String(memberId));
            if (!entry) return;
            const user = entry.user || {};
            memberTitle.textContent = user.game_nickname || 'Игрок';
            const roleInfo = memberRoleMap[user.role] || memberRoleMap.fighter;
            memberRole.textContent = roleInfo.name;
            memberRole.className = 'member-modal-role ' + roleInfo.css;
            memberClass.textContent = memberClassMap[user.class_key] || 'Боец Авангарда';
            renderMiniProfile(entry);
            memberModal.classList.add('open');
            memberModal.setAttribute('aria-hidden', 'false');
            document.body.classList.add('member-modal-open');
        }

        document.querySelectorAll('.js-member-card').forEach(card => {
            card.addEventListener('click', () => openMemberModal(card.dataset.memberId));
        });
        memberModal.querySelectorAll('[data-member-close]').forEach(el => el.addEventListener('click', closeMemberModal));
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && memberModal.classList.contains('open')) closeMemberModal();
        });
    }

    // Календарь мероприятий и отметка присутствия.
    const attendanceModal = document.getElementById('attendance-day-modal');
    const attendancePlayers = document.getElementById('attendance-day-players');
    const attendanceTitle = document.getElementById('attendance-day-title');
    const attendanceSubtitle = document.getElementById('attendance-day-subtitle');
    const attendanceNote = document.getElementById('attendance-day-note');
    if (attendanceModal && attendancePlayers) {
        const roleCss = { chief:'role-chief', officer:'role-officer', sergeant:'role-sergeant', fighter:'role-fighter' };
        const classNames = {
            vanguard_fighter:'Боец Авангарда', berserk:'Берсерк', destroyer:'Разрушитель',
            night_tracker:'Ночной следопыт', elemental_master:'Мастер стихий', sky_caster:'Небесный заклинатель',
            assassin:'Убийца', deathdealer:'Смертоносец', shooter:'Стрелок', warlord:'Военачальник'
        };
        const classIcon = key => `/static/game_catalog/class/${key || 'vanguard_fighter'}/icon.png`;
        const formatPlayer = (player, eventType, eventDate, canEditAny, mode, currentUserId) => {
            const editable = canEditAny || (mode === 'self' && String(player.id) === String(currentUserId));
            const checked = player.present ? 'checked' : '';
            const disabled = editable ? '' : 'disabled';
            const image = player.character_card
                ? `<img src="${escapeHtml(player.character_card)}" alt="">`
                : `<img src="${classIcon(player.class_key)}" alt="">`;
            return `<label class="attendance-player-row ${player.present ? 'present' : ''} ${editable ? 'editable' : 'readonly'} ${roleCss[player.role_key] || 'role-fighter'}">
                <div class="attendance-player-avatar">${image}</div>
                <div class="attendance-player-info"><strong>${escapeHtml(player.nickname || 'Игрок')}</strong><span>${escapeHtml(player.role || '')} · ${escapeHtml(classNames[player.class_key] || '')}</span></div>
                <div class="attendance-player-check"><input type="checkbox" data-attendance-checkbox data-user-id="${player.id}" data-event-type="${escapeHtml(eventType)}" data-event-date="${escapeHtml(eventDate)}" ${checked} ${disabled}><span>Присутствовал</span></div>
            </label>`;
        };
        const closeAttendance = () => {
            attendanceModal.classList.remove('open');
            attendanceModal.setAttribute('aria-hidden','true');
            document.body.classList.remove('catalog-modal-open');
        };
        const openDay = async (eventType, eventDate) => {
            attendanceModal.classList.add('open');
            attendanceModal.setAttribute('aria-hidden','false');
            document.body.classList.add('catalog-modal-open');
            attendancePlayers.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⌛</div><p>Загрузка...</p></div>';
            try {
                const resp = await fetch(`/events/day?event_type=${encodeURIComponent(eventType)}&event_date=${encodeURIComponent(eventDate)}`, {credentials:'same-origin'});
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.detail || 'Не удалось загрузить состав.');
                attendanceTitle.textContent = data.event_name;
                attendanceSubtitle.textContent = data.event_date_display;
                attendanceNote.textContent = data.attendance_mode === 'self'
                    ? 'Каждый активный игрок может отмечать только себя. Системный аккаунт может отмечать любого активного игрока.'
                    : 'Сейчас отметку может изменять только системный аккаунт.';
                attendancePlayers.innerHTML = data.players.length
                    ? data.players.map(p => formatPlayer(p, data.event_type, data.event_date, data.can_edit_any, data.attendance_mode, data.current_user_id)).join('')
                    : '<div class="empty-state"><div class="empty-state-icon">👥</div><p>В активном составе пока нет игроков.</p></div>';
            } catch (error) {
                attendancePlayers.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><p>${escapeHtml(error.message || 'Ошибка загрузки.')}</p></div>`;
            }
        };
        document.querySelectorAll('.js-event-day').forEach(day => {
            day.addEventListener('click', () => openDay(day.dataset.eventType, day.dataset.eventDate));
        });
        attendanceModal.querySelectorAll('[data-attendance-close]').forEach(el => el.addEventListener('click', closeAttendance));
        attendancePlayers.addEventListener('change', async event => {
            const input = event.target.closest('[data-attendance-checkbox]');
            if (!input || input.disabled) return;
            input.disabled = true;
            const fd = new FormData();
            fd.append('event_type', input.dataset.eventType);
            fd.append('event_date', input.dataset.eventDate);
            fd.append('user_id', input.dataset.userId);
            fd.append('present', input.checked ? '1' : '0');
            try {
                const resp = await fetch('/events/attendance', {method:'POST', body:fd, credentials:'same-origin'});
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.ok) throw new Error(data.detail || 'Не удалось сохранить отметку.');
                input.closest('.attendance-player-row')?.classList.toggle('present', input.checked);
            } catch (error) {
                input.checked = !input.checked;
                alert(error.message || 'Ошибка сохранения.');
            } finally { input.disabled = false; }
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        if (modal && modal.classList.contains('open')) closeModal();
        if (classModal && classModal.classList.contains('open')) {
            classModal.classList.remove('open');
            classModal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('catalog-modal-open');
        }
        if (attendanceModal && attendanceModal.classList.contains('open')) {
            attendanceModal.classList.remove('open');
            attendanceModal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('catalog-modal-open');
        }
    });
})();
