(function() {
  function updatePlayersForFixture(fixtureId) {
    if (!fixtureId) return;
    fetch('/admin/league/match/players-for-fixture/?fixture_id=' + fixtureId)
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var homeSel = document.getElementById('id_home_players');
        var awaySel = document.getElementById('id_away_players');

        if (homeSel) {
          updateSelectOptions(homeSel, data.home);
        }
        if (awaySel) {
          updateSelectOptions(awaySel, data.away);
        }

        // Inline player selects (PlayerMatchStatsInline) - combine both lists
        var inlinePlayerSelects = document.querySelectorAll('select[name$="-player"]');
        inlinePlayerSelects.forEach(function(select) {
          var combined = (data.home || []).concat(data.away || []);
          updateSelectOptions(select, combined, true);
        });
      }).catch(function(err) {
        console.error('Failed to fetch players for fixture', err);
      });
  }

  function updateSelectOptions(selectEl, players, keepValueIfPresent) {
    var prevValue = Array.from(selectEl.options).filter(function(o){ return o.selected; }).map(function(o){ return o.value; });
    selectEl.innerHTML = '';

    players.forEach(function(p) {
      var opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.gamertag;
      selectEl.appendChild(opt);
    });

    if (prevValue.length && keepValueIfPresent) {
      prevValue.forEach(function(v) {
        var option = selectEl.querySelector('option[value="' + v + '"]');
        if (option) option.selected = true;
      });
    }

    // Fire change event for any admin handlers
    selectEl.dispatchEvent(new Event('change'));
  }

  document.addEventListener('DOMContentLoaded', function() {
    var fixtureSelect = document.getElementById('id_fixture');
    if (!fixtureSelect) return;

    // On load, if fixture has a value, fetch players
    if (fixtureSelect.value) {
      updatePlayersForFixture(fixtureSelect.value);
    }

    fixtureSelect.addEventListener('change', function() {
      updatePlayersForFixture(this.value);
    });
  });
})();
