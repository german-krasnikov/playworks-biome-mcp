"""RED: FlagDiscovery — regex scan jakefile for flag names."""
import pytest

from luna_mcp.flag_explorer.discovery import scan_jakefile_flags

SAMPLE_JAKEFILE = """
// Jakefile.js sample
var config = require('./config.js');

task('build', function() {
    var minify = luna.json["disableMinify"];
    var compress = config["compressTexturesWebP"];
    var opt = getOption("useUnstableSolver");
    var log = luna.json['enableConsoleLogging'];
    var tex = getOption('forceUncompressedTextures');
    // dupe reference for count check
    var minify2 = luna.json["disableMinify"];
});
"""


@pytest.fixture
def jakefile(tmp_path):
    p = tmp_path / "Jakefile.js"
    p.write_text(SAMPLE_JAKEFILE)
    return p


def test_scan_returns_dict(jakefile):
    result = scan_jakefile_flags(jakefile)
    assert isinstance(result, dict)


def test_scan_luna_json_pattern(jakefile):
    result = scan_jakefile_flags(jakefile)
    assert "disableMinify" in result
    assert "enableConsoleLogging" in result


def test_scan_config_pattern(jakefile):
    result = scan_jakefile_flags(jakefile)
    assert "compressTexturesWebP" in result


def test_scan_get_option_pattern(jakefile):
    result = scan_jakefile_flags(jakefile)
    assert "useUnstableSolver" in result
    assert "forceUncompressedTextures" in result


def test_scan_locations_have_source_label(jakefile):
    result = scan_jakefile_flags(jakefile)
    locs = result["disableMinify"]
    assert any("luna_json" in loc for loc in locs)


def test_scan_locations_have_line_numbers(jakefile):
    result = scan_jakefile_flags(jakefile)
    locs = result["disableMinify"]
    assert any("line" in loc for loc in locs)


def test_scan_multiple_references_counted(jakefile):
    result = scan_jakefile_flags(jakefile)
    # disableMinify appears twice in the sample
    assert len(result["disableMinify"]) == 2


def test_scan_missing_file_returns_empty(tmp_path):
    result = scan_jakefile_flags(tmp_path / "nonexistent.js")
    assert result == {}


def test_scan_empty_file_returns_empty(tmp_path):
    p = tmp_path / "Jakefile.js"
    p.write_text("")
    result = scan_jakefile_flags(p)
    assert result == {}


def test_scan_config_locations_have_label(jakefile):
    result = scan_jakefile_flags(jakefile)
    locs = result["compressTexturesWebP"]
    assert any("config" in loc for loc in locs)


def test_scan_get_option_locations_have_label(jakefile):
    result = scan_jakefile_flags(jakefile)
    locs = result["useUnstableSolver"]
    assert any("getOption" in loc for loc in locs)


def test_discover_matches_dot_access(tmp_path):
    """M2: luna.json.disableMinify dot syntax must be discovered."""
    p = tmp_path / "Jakefile.js"
    p.write_text("var x = luna.json.disableMinify;")
    result = scan_jakefile_flags(p)
    assert "disableMinify" in result


def test_discover_skips_config_noise(tmp_path):
    """M3: known noisy config keys like 'path' must be suppressed."""
    p = tmp_path / "Jakefile.js"
    p.write_text("var x = config['path'];")
    result = scan_jakefile_flags(p)
    assert "path" not in result
