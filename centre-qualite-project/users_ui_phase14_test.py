from pathlib import Path


APP = Path('static/app.js').read_text(encoding='utf-8')
CSS = Path('static/style.css').read_text(encoding='utf-8')


def test_users_ui_is_split_into_four_clear_tabs():
    for key, label in [
        ('accounts', 'Comptes'),
        ('groups', 'Groupes d’accès'),
        ('profiles', 'Profils'),
        ('effective', 'Droits effectifs'),
    ]:
        assert f'data-tab="{key}"' in APP
        assert label in APP


def test_group_editor_is_single_selection_workspace_not_all_cards_expanded():
    assert 'access-groups-workspace' in APP
    assert 'id="access-group-editor"' in APP
    assert 'renderGroupEditor' in APP
    assert 'access-group-list-item' in APP
    assert 'access-perm-section' in APP


def test_accounts_have_search_filters_and_bulk_assignment():
    for marker in [
        'access-user-search',
        'access-user-status',
        'access-user-group',
        'access-select-visible',
        'access-bulk-group',
        'access-bulk-apply',
    ]:
        assert marker in APP
    assert "'/api/access-groups/member'" in APP


def test_effective_rights_preview_is_read_only_and_uses_backend_effective_permissions():
    assert 'access-effective-user' in APP
    assert 'effective_interface_permissions' in APP
    assert 'effective_group_scope' in APP
    assert 'Interfaces réellement accessibles' in APP
    assert 'Résultat calculé par le backend pour ce compte.' in APP


def test_create_forms_are_collapsible_instead_of_permanently_visible():
    assert 'user-create-details' in APP
    assert 'access-group-create-details' in APP
    assert 'access-profile-create-details' in APP
    assert 'access-create-box' in CSS


def test_phase14_has_responsive_compact_workspace_styles():
    for selector in [
        '.access-tabs',
        '.access-toolbar',
        '.access-groups-workspace',
        '.access-group-editor-card',
        '.access-effective-summary',
    ]:
        assert selector in CSS
    assert '@media(max-width:760px)' in CSS


def test_no_inline_event_handlers_were_added_to_users_ui():
    block = APP[APP.index('let usersUiState='):APP.index('\nlet classificationSection=')]
    assert ' onclick=' not in block
    assert ' onchange=' not in block
