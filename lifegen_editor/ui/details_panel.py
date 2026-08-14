"""The 4th pane: edit a cat's non-appearance ("details") fields, plus the
per-cat Health/Relationships sidecar files and the clan-level file.

Unlike the appearance editor this pane does not live-render; each concern has an
explicit *Apply* button that writes (with a backup) to the matching file. All
option lists are filtered to the loaded save's :class:`GameVariant`, and the
LifeGen-only groups (Skills, Faith, LifeGen stats) are hidden for ClanGen saves.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..io import CatDetails
from ..saves import (
    Clan,
    GameVariant,
    detect_variant,
    write_clan_with_backup,
    load_conditions,
    write_conditions,
    load_relationships,
    write_relationships,
    load_clan_json,
    write_clan_json,
    default_condition_entry,
    remove_from_afterlife,
)
from . import options as opt

_REL_STATS = [
    "romantic_love", "platonic_like", "dislike", "admiration",
    "comfortable", "jealousy", "trust",
]
_CONDITION_BUCKETS = [
    ("illnesses", "Illness", opt.ILLNESSES),
    ("injuries", "Injury", opt.INJURIES),
    ("permanent conditions", "Permanent", opt.PERMANENT_CONDITIONS),
]


def _spin(lo: int, hi: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    return s


def _opt_combo(items: list[str]) -> QComboBox:
    box = QComboBox()
    box.addItem("(none)", userData=None)
    for i in items:
        box.addItem(i, userData=i)
    return box


class DetailsPanel(QScrollArea):
    applied = Signal()  # main_window refreshes the save-panel cat label

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clan: Optional[Clan] = None
        self._index: int = -1
        self._variant = GameVariant.LIFEGEN
        self.details = CatDetails()
        self._conditions: dict = {}
        self._relationships: list[dict] = []
        self._clan_json: Optional[dict] = None
        self._loading = False

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.setWidget(body)
        self._v = QVBoxLayout(body)
        self._v.setContentsMargins(8, 8, 8, 8)
        self._v.setSpacing(8)

        self._placeholder = QLabel("Pick a cat to edit its details.")
        self._placeholder.setWordWrap(True)
        self._v.addWidget(self._placeholder)

        self._v.addWidget(self._build_identity())
        self._v.addWidget(self._build_status())
        self._v.addWidget(self._build_life())
        self._v.addWidget(self._build_personality())
        self._v.addWidget(self._build_skills())
        self._v.addWidget(self._build_faith())
        self._v.addWidget(self._build_flags())
        self._v.addWidget(self._build_stats())
        self._apply_btn = QPushButton("Apply cat details → save")
        self._apply_btn.clicked.connect(self._apply_details)
        self._v.addWidget(self._apply_btn)
        self._v.addWidget(self._build_health())
        self._v.addWidget(self._build_relationships())
        self._v.addWidget(self._build_clan())
        self._v.addStretch(1)
        self._set_enabled(False)

    # ---------- core-field groups ----------
    def _build_identity(self) -> QGroupBox:
        g = QGroupBox("Identity")
        f = QFormLayout(g)
        self.prefix_edit = QLineEdit()
        self.suffix_edit = QLineEdit()
        f.addRow("Name prefix", self.prefix_edit)
        f.addRow("Name suffix", self.suffix_edit)
        self.gender_combo = QComboBox()
        self.gender_align_combo = QComboBox()
        f.addRow("Sex", self.gender_combo)
        f.addRow("Gender align", self.gender_align_combo)
        return g

    def _build_status(self) -> QGroupBox:
        g = QGroupBox("Status / rank")
        f = QFormLayout(g)
        self.status_combo = QComboBox()
        f.addRow("Status", self.status_combo)
        self.experience_spin = _spin(0, 321)
        f.addRow("Experience", self.experience_spin)
        return g

    def _build_life(self) -> QGroupBox:
        g = QGroupBox("Life and death")
        f = QFormLayout(g)
        self.moons_spin = _spin(0, 600)
        self.age_label = QLabel("")
        self.moons_spin.valueChanged.connect(
            lambda v: self.age_label.setText(f"→ {opt.age_stage(v)}")
        )
        moons_row = QHBoxLayout()
        moons_row.addWidget(self.moons_spin)
        moons_row.addWidget(self.age_label)
        moons_row.addStretch(1)
        mw = QWidget()
        mw.setLayout(moons_row)
        f.addRow("Age (moons)", mw)

        self.dead_cb = QCheckBox("Dead")
        self.df_cb = QCheckBox("Dark Forest (vs StarClan)")
        self.outside_cb = QCheckBox("Outside the clan")
        self.exiled_cb = QCheckBox("Exiled")
        self.prevent_fading_cb = QCheckBox("Prevent fading")
        for cb in (self.dead_cb, self.df_cb, self.outside_cb, self.exiled_cb,
                   self.prevent_fading_cb):
            f.addRow(cb)
        self.dead_moons_spin = _spin(0, 600)
        f.addRow("Moons dead", self.dead_moons_spin)
        self.resurrect_btn = QPushButton("Resurrect this cat")
        self.resurrect_btn.clicked.connect(self._resurrect)
        f.addRow(self.resurrect_btn)
        return g

    def _build_personality(self) -> QGroupBox:
        g = QGroupBox("Personality")
        f = QFormLayout(g)
        self.trait_combo = QComboBox()
        self.trait_combo.addItems(opt.traits())
        f.addRow("Trait", self.trait_combo)
        self.facet_spins = {}
        for name in opt.FACET_NAMES:
            s = _spin(opt.FACET_MIN, opt.FACET_MAX)
            self.facet_spins[name] = s
            f.addRow(name.capitalize(), s)
        return g

    def _build_skills(self) -> QGroupBox:
        g = QGroupBox("Skills")
        f = QFormLayout(g)
        self.skill_primary_combo = _opt_combo([])
        self.skill_primary_points = _spin(opt.SKILL_POINTS_MIN, opt.SKILL_POINTS_MAX)
        self.skill_secondary_combo = _opt_combo([])
        self.skill_secondary_points = _spin(opt.SKILL_POINTS_MIN, opt.SKILL_POINTS_MAX)
        f.addRow("Primary path", self.skill_primary_combo)
        f.addRow("Primary points", self.skill_primary_points)
        f.addRow("Secondary path", self.skill_secondary_combo)
        f.addRow("Secondary points", self.skill_secondary_points)
        self._skills_group = g
        return g

    def _build_faith(self) -> QGroupBox:
        g = QGroupBox("Faith (LifeGen)")
        f = QFormLayout(g)
        self.faith_spin = _spin(opt.FAITH_MIN, opt.FAITH_MAX)
        f.addRow("Faith", self.faith_spin)
        self.no_faith_cb = QCheckBox("No faith")
        f.addRow(self.no_faith_cb)
        self.lock_faith_combo = QComboBox()
        self.lock_faith_combo.addItems(opt.LOCK_FAITH_VALUES)
        f.addRow("Lock faith", self.lock_faith_combo)
        self._faith_group = g
        return g

    def _build_flags(self) -> QGroupBox:
        g = QGroupBox("Behaviour flags")
        f = QFormLayout(g)
        self.no_kits_cb = QCheckBox("No kits")
        self.no_mates_cb = QCheckBox("No mates")
        self.no_retire_cb = QCheckBox("No retire")
        self.favourite_cb = QCheckBox("Favourite")
        for cb in (self.no_kits_cb, self.no_mates_cb, self.no_retire_cb, self.favourite_cb):
            f.addRow(cb)
        return g

    def _build_stats(self) -> QGroupBox:
        g = QGroupBox("LifeGen stats")
        f = QFormLayout(g)
        self.stat_spins = {}
        for name in ("courage", "compassion", "intelligence", "empathy"):
            s = _spin(0, 20)
            self.stat_spins[name] = s
            f.addRow(name.capitalize(), s)
        self._stats_group = g
        return g

    # ---------- health ----------
    def _build_health(self) -> QGroupBox:
        g = QGroupBox("Health / conditions")
        v = QVBoxLayout(g)
        self._cond_lists: dict[str, QListWidget] = {}
        self._cond_combos: dict[str, QComboBox] = {}
        for bucket, label, ids in _CONDITION_BUCKETS:
            v.addWidget(QLabel(f"<b>{label}</b>"))
            row = QHBoxLayout()
            combo = QComboBox()
            combo.addItems(ids)
            row.addWidget(combo, 1)
            add = QPushButton("Add")
            add.clicked.connect(lambda _=False, b=bucket: self._add_condition(b))
            row.addWidget(add)
            rm = QPushButton("×")
            rm.clicked.connect(lambda _=False, b=bucket: self._remove_condition(b))
            row.addWidget(rm)
            v.addLayout(row)
            lst = QListWidget()
            lst.setMaximumHeight(70)
            v.addWidget(lst)
            self._cond_lists[bucket] = lst
            self._cond_combos[bucket] = combo
        apply_btn = QPushButton("Apply health → conditions file")
        apply_btn.clicked.connect(self._apply_health)
        v.addWidget(apply_btn)
        return g

    # ---------- relationships ----------
    def _build_relationships(self) -> QGroupBox:
        g = QGroupBox("Relationships")
        v = QVBoxLayout(g)
        add_row = QHBoxLayout()
        self.rel_target_combo = QComboBox()
        add_row.addWidget(self.rel_target_combo, 1)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_relationship)
        add_row.addWidget(add_btn)
        v.addLayout(add_row)

        self.rel_list = QListWidget()
        self.rel_list.setMaximumHeight(90)
        self.rel_list.currentRowChanged.connect(self._on_rel_selected)
        v.addWidget(self.rel_list)

        form = QFormLayout()
        self.rel_stat_spins = {}
        for stat in _REL_STATS:
            s = _spin(0, 100)
            s.valueChanged.connect(self._on_rel_stat_changed)
            self.rel_stat_spins[stat] = s
            form.addRow(stat.replace("_", " ").capitalize(), s)
        self.rel_mates_cb = QCheckBox("Mates")
        self.rel_mates_cb.toggled.connect(self._on_rel_stat_changed)
        self.rel_family_cb = QCheckBox("Family")
        self.rel_family_cb.toggled.connect(self._on_rel_stat_changed)
        form.addRow(self.rel_mates_cb)
        form.addRow(self.rel_family_cb)
        v.addLayout(form)

        apply_btn = QPushButton("Apply relationships → file")
        apply_btn.clicked.connect(self._apply_relationships)
        v.addWidget(apply_btn)
        return g

    # ---------- clan ----------
    def _build_clan(self) -> QGroupBox:
        g = QGroupBox("Clan")
        f = QFormLayout(g)
        self.clan_leader_combo = _opt_combo([])
        self.clan_deputy_combo = _opt_combo([])
        self.clan_med_combo = _opt_combo([])
        f.addRow("Leader", self.clan_leader_combo)
        f.addRow("Deputy", self.clan_deputy_combo)
        f.addRow("Healer / med cat", self.clan_med_combo)
        self.clan_lives_spin = _spin(0, 9)
        f.addRow("Leader lives", self.clan_lives_spin)
        self.clan_age_spin = _spin(0, 10000)
        f.addRow("Clan age (moons)", self.clan_age_spin)
        self.clan_rep_spin = _spin(0, 200)
        f.addRow("Reputation", self.clan_rep_spin)
        self.clan_biome_combo = QComboBox()
        self.clan_biome_combo.addItems(opt.BIOMES)
        f.addRow("Biome", self.clan_biome_combo)
        self.clan_roster_label = QLabel("")
        f.addRow("Afterlife", self.clan_roster_label)
        apply_btn = QPushButton("Apply clan → clan file")
        apply_btn.clicked.connect(self._apply_clan)
        f.addRow(apply_btn)
        self._clan_group = g
        return g

    # ================= load =================
    def load_from_pick(self, clan: Clan, index: int) -> None:
        self._clan = clan
        self._index = index
        self._variant = detect_variant(clan)
        cat = clan.cats[index]
        self.details = CatDetails.from_save_cat(cat.raw, self._variant)
        self._conditions = load_conditions(clan, cat.cat_id)
        self._relationships = load_relationships(clan, cat.cat_id)
        self._clan_json = None  # lazy
        self._placeholder.setVisible(False)
        self._set_enabled(True)
        self._apply_variant_visibility()
        self._reload_variant_combos()
        self._load_widgets()
        self._load_health_widgets()
        self._load_relationship_widgets()
        self._ensure_clan_json()

    def _apply_variant_visibility(self) -> None:
        lifegen = self._variant.is_lifegen
        for grp in (self._skills_group, self._faith_group, self._stats_group):
            grp.setVisible(lifegen)

    def _reload_variant_combos(self) -> None:
        legacy_status = not isinstance(self.details._status_raw, dict)
        self._fill_combo(self.status_combo,
                         opt.statuses(self._variant, legacy_status=legacy_status))
        self._fill_combo(self.gender_combo, opt.genders(self._variant))
        self._fill_combo(self.gender_align_combo, opt.gender_aligns(self._variant))
        self._fill_combo(self.trait_combo, opt.traits(self._variant))
        self._fill_opt_combo(self.skill_primary_combo, opt.skill_paths(self._variant))
        self._fill_opt_combo(self.skill_secondary_combo, opt.skill_paths(self._variant))
        for bucket, _label, ids in _CONDITION_BUCKETS:
            self._fill_combo(self._cond_combos[bucket],
                             opt.conditions_for(ids, self._variant))

    @staticmethod
    def _fill_combo(combo: QComboBox, items: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        combo.blockSignals(False)

    @staticmethod
    def _fill_opt_combo(combo: QComboBox, items: list[str]) -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("(none)", userData=None)
        for i in items:
            combo.addItem(i, userData=i)
        combo.blockSignals(False)

    def _load_widgets(self) -> None:
        self._loading = True
        try:
            d = self.details
            self.prefix_edit.setText(d.name_prefix)
            self.suffix_edit.setText(d.name_suffix)
            self._set_combo_text(self.gender_combo, d.gender)
            self._set_combo_text(self.gender_align_combo, d.gender_align)
            self._set_combo_text(self.status_combo, d.status)
            self.experience_spin.setValue(d.experience)
            self.moons_spin.setValue(d.moons)
            self.age_label.setText(f"→ {opt.age_stage(d.moons)}")
            self.dead_cb.setChecked(d.dead)
            self.df_cb.setChecked(d.df)
            self.outside_cb.setChecked(d.outside)
            self.exiled_cb.setChecked(d.exiled)
            self.prevent_fading_cb.setChecked(d.prevent_fading)
            self.dead_moons_spin.setValue(d.dead_moons)
            self._set_combo_text(self.trait_combo, d.trait)
            self.facet_spins["lawfulness"].setValue(d.facet_lawfulness)
            self.facet_spins["sociability"].setValue(d.facet_sociability)
            self.facet_spins["aggression"].setValue(d.facet_aggression)
            self.facet_spins["stability"].setValue(d.facet_stability)
            self._set_combo_data(self.skill_primary_combo, d.skill_primary_path)
            self.skill_primary_points.setValue(d.skill_primary_points)
            self._set_combo_data(self.skill_secondary_combo, d.skill_secondary_path)
            self.skill_secondary_points.setValue(d.skill_secondary_points)
            self.faith_spin.setValue(d.faith)
            self.no_faith_cb.setChecked(d.no_faith)
            self._set_combo_text(self.lock_faith_combo, d.lock_faith)
            self.no_kits_cb.setChecked(d.no_kits)
            self.no_mates_cb.setChecked(d.no_mates)
            self.no_retire_cb.setChecked(d.no_retire)
            self.favourite_cb.setChecked(d.favourite)
            for name, spin in self.stat_spins.items():
                spin.setValue(getattr(d, name))
        finally:
            self._loading = False

    def _read_widgets(self) -> None:
        d = self.details
        d.name_prefix = self.prefix_edit.text()
        d.name_suffix = self.suffix_edit.text()
        d.gender = self.gender_combo.currentText()
        d.gender_align = self.gender_align_combo.currentText()
        d.status = self.status_combo.currentText()
        d.experience = self.experience_spin.value()
        d.moons = self.moons_spin.value()
        d.dead = self.dead_cb.isChecked()
        d.df = self.df_cb.isChecked()
        d.outside = self.outside_cb.isChecked()
        d.exiled = self.exiled_cb.isChecked()
        d.prevent_fading = self.prevent_fading_cb.isChecked()
        d.dead_moons = self.dead_moons_spin.value()
        d.trait = self.trait_combo.currentText()
        d.facet_lawfulness = self.facet_spins["lawfulness"].value()
        d.facet_sociability = self.facet_spins["sociability"].value()
        d.facet_aggression = self.facet_spins["aggression"].value()
        d.facet_stability = self.facet_spins["stability"].value()
        d.skill_primary_path = self.skill_primary_combo.currentData()
        d.skill_primary_points = self.skill_primary_points.value()
        d.skill_secondary_path = self.skill_secondary_combo.currentData()
        d.skill_secondary_points = self.skill_secondary_points.value()
        d.faith = self.faith_spin.value()
        d.no_faith = self.no_faith_cb.isChecked()
        d.lock_faith = self.lock_faith_combo.currentText()
        d.no_kits = self.no_kits_cb.isChecked()
        d.no_mates = self.no_mates_cb.isChecked()
        d.no_retire = self.no_retire_cb.isChecked()
        d.favourite = self.favourite_cb.isChecked()
        for name, spin in self.stat_spins.items():
            setattr(d, name, spin.value())

    # ================= apply: core =================
    def _apply_details(self) -> None:
        if not self._confirm("cat details"):
            return
        self._read_widgets()
        cat = self._clan.cats[self._index]
        try:
            self.details.apply_to_save_cat(cat.raw, self._variant)
            backup = write_clan_with_backup(self._clan)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._report(backup)
        self.applied.emit()

    def _resurrect(self) -> None:
        if self._clan is None:
            return
        if QMessageBox.question(
            self, "Resurrect",
            "Bring this cat back to life? This clears its death flags and removes "
            "it from the StarClan / Dark Forest / Unknown rosters.\n\nBackups of "
            "both clan_cats.json and the clan file will be made first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._read_widgets()
        self.details.clear_death()
        cat = self._clan.cats[self._index]
        try:
            self.details.apply_to_save_cat(cat.raw, self._variant)
            write_clan_with_backup(self._clan)
            cj = self._ensure_clan_json()
            pruned = remove_from_afterlife(cj, cat.cat_id)
            self._clan_json = pruned
            write_clan_json(self._clan, pruned)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Resurrect failed", str(e))
            return
        self._load_widgets()
        self._load_clan_widgets()
        self._report(None, "Resurrected.")
        self.applied.emit()

    # ================= health =================
    def _load_health_widgets(self) -> None:
        for bucket, _label, _ids in _CONDITION_BUCKETS:
            lst = self._cond_lists[bucket]
            lst.clear()
            for name in self._conditions.get(bucket, {}):
                lst.addItem(name)

    def _add_condition(self, bucket: str) -> None:
        name = self._cond_combos[bucket].currentText()
        if not name:
            return
        self._conditions.setdefault(bucket, {})
        if name not in self._conditions[bucket]:
            self._conditions[bucket][name] = default_condition_entry(bucket)
            self._load_health_widgets()

    def _remove_condition(self, bucket: str) -> None:
        lst = self._cond_lists[bucket]
        item = lst.currentItem()
        if item is None:
            return
        self._conditions.get(bucket, {}).pop(item.text(), None)
        self._load_health_widgets()

    def _apply_health(self) -> None:
        if self._clan is None or not self._confirm("health / conditions"):
            return
        cat = self._clan.cats[self._index]
        try:
            backup = write_conditions(self._clan, cat.cat_id, self._conditions)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._report(backup)
        self.applied.emit()

    # ================= relationships =================
    def _cat_name(self, cat_id: str) -> str:
        for c in self._clan.cats:
            if c.cat_id == cat_id:
                return c.display_name
        return cat_id

    def _load_relationship_widgets(self) -> None:
        # populate add-target combo with the other cats
        self.rel_target_combo.clear()
        me = self._clan.cats[self._index].cat_id
        existing = {r.get("cat_to_id") for r in self._relationships}
        for c in self._clan.cats:
            if c.cat_id != me and c.cat_id not in existing:
                self.rel_target_combo.addItem(c.display_name, userData=c.cat_id)
        self.rel_list.clear()
        for r in self._relationships:
            self.rel_list.addItem(self._cat_name(r.get("cat_to_id", "?")))
        if self._relationships:
            self.rel_list.setCurrentRow(0)
        else:
            self._show_rel_record(None)

    def _on_rel_selected(self, row: int) -> None:
        rec = self._relationships[row] if 0 <= row < len(self._relationships) else None
        self._show_rel_record(rec)

    def _show_rel_record(self, rec: Optional[dict]) -> None:
        self._loading = True
        try:
            for stat in _REL_STATS:
                self.rel_stat_spins[stat].setValue(int(rec.get(stat, 0)) if rec else 0)
            self.rel_mates_cb.setChecked(bool(rec.get("mates")) if rec else False)
            self.rel_family_cb.setChecked(bool(rec.get("family")) if rec else False)
        finally:
            self._loading = False

    def _on_rel_stat_changed(self, *_args) -> None:
        if self._loading:
            return
        row = self.rel_list.currentRow()
        if not (0 <= row < len(self._relationships)):
            return
        rec = self._relationships[row]
        for stat in _REL_STATS:
            rec[stat] = self.rel_stat_spins[stat].value()
        rec["mates"] = self.rel_mates_cb.isChecked()
        rec["family"] = self.rel_family_cb.isChecked()

    def _add_relationship(self) -> None:
        target = self.rel_target_combo.currentData()
        if not target:
            return
        me = self._clan.cats[self._index].cat_id
        rec = {"cat_from_id": me, "cat_to_id": target, "mates": False, "family": False,
               "log": []}
        for stat in _REL_STATS:
            rec[stat] = 0
        self._relationships.append(rec)
        self._load_relationship_widgets()
        self.rel_list.setCurrentRow(len(self._relationships) - 1)

    def _apply_relationships(self) -> None:
        if self._clan is None or not self._confirm("relationships"):
            return
        cat = self._clan.cats[self._index]
        try:
            backup = write_relationships(self._clan, cat.cat_id, self._relationships)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._report(backup)
        self.applied.emit()

    # ================= clan =================
    def _ensure_clan_json(self) -> dict:
        if self._clan_json is None:
            self._clan_json = load_clan_json(self._clan)
            self._load_clan_widgets()
        return self._clan_json

    def _load_clan_widgets(self) -> None:
        cj = self._clan_json or {}
        ids = [c.cat_id for c in self._clan.cats]
        for combo, key in ((self.clan_leader_combo, "leader"),
                           (self.clan_deputy_combo, "deputy"),
                           (self.clan_med_combo, "med_cat")):
            self._fill_opt_combo(combo, ids)
            self._set_combo_data(combo, cj.get(key))
        self.clan_lives_spin.setValue(int(cj.get("leader_lives", 9) or 0))
        # LifeGen v0.7.7 renamed clanage -> clan_age; read whichever exists.
        age = cj.get("clanage", cj.get("clan_age", 0))
        self.clan_age_spin.setValue(int(age) if isinstance(age, (int, float)) else 0)
        self.clan_rep_spin.setValue(int(cj.get("reputation", 0) or 0))
        self._set_combo_text(self.clan_biome_combo, str(cj.get("biome", "Forest")))
        rosters = []
        for key in ("starclan_cats", "darkforest_cats", "unknown_cats"):
            val = cj.get(key)
            n = len(val) if isinstance(val, list) else (len(val.split(",")) if val else 0)
            rosters.append(f"{key.split('_')[0]}: {n}")
        self.clan_roster_label.setText("  ".join(rosters))

    def _apply_clan(self) -> None:
        if self._clan is None:
            return
        cj = dict(self._ensure_clan_json())
        if self.clan_leader_combo.currentData():
            cj["leader"] = self.clan_leader_combo.currentData()
        if self.clan_deputy_combo.currentData():
            cj["deputy"] = self.clan_deputy_combo.currentData()
        if self.clan_med_combo.currentData():
            cj["med_cat"] = self.clan_med_combo.currentData()
        cj["leader_lives"] = self.clan_lives_spin.value()
        # Write the clan age back under whichever key the save already uses.
        if "clan_age" in self._clan_json:
            cj["clan_age"] = self.clan_age_spin.value()
        elif isinstance(self._clan_json.get("clanage"), (int, float)) or "clanage" not in self._clan_json:
            cj["clanage"] = self.clan_age_spin.value()
        cj["reputation"] = self.clan_rep_spin.value()
        cj["biome"] = self.clan_biome_combo.currentText()
        if not self._confirm("clan settings"):
            return
        try:
            backup = write_clan_json(self._clan, cj)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._clan_json = cj
        self._report(backup)
        self.applied.emit()

    # ================= helpers =================
    def _confirm(self, what: str) -> bool:
        cat = self._clan.cats[self._index]
        return QMessageBox.question(
            self, "Apply",
            f"Write {what} for {cat.display_name} in “{self._clan.name}”?\n\n"
            "A timestamped backup will be created first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _report(self, backup, msg: str = "Saved.") -> None:
        win = self.window()
        if hasattr(win, "statusBar"):
            tail = f" Backup: {backup.name}" if backup else ""
            win.statusBar().showMessage(msg + tail)

    def _set_enabled(self, on: bool) -> None:
        body = self.widget()
        for child in body.findChildren(QGroupBox):
            child.setEnabled(on)
        self._apply_btn.setEnabled(on)

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str) -> None:
        ix = combo.findText(value)
        if ix < 0 and value:
            combo.addItem(value)
            ix = combo.findText(value)
        combo.setCurrentIndex(max(0, ix))

    @staticmethod
    def _set_combo_data(combo: QComboBox, value) -> None:
        ix = combo.findData(value)
        combo.setCurrentIndex(ix if ix >= 0 else 0)
