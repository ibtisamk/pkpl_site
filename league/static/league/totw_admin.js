(function($) {
    'use strict';
    
    $(document).ready(function() {
        // Handle TOTW selection admin
        if (window.location.href.indexOf('/league/teamoftheweekselection/') > -1) {
            setupTOTWSelectionAdmin();
        }
        
        // Handle TOTW inline in TeamOfTheWeek admin
        if (window.location.href.indexOf('/league/teamoftheweek/') > -1) {
            setupTOTWInlines();
        }
    });
    
    function setupTOTWSelectionAdmin() {
        const positionField = $('#id_position');
        const playerField = $('#id_player');
        
        if (positionField.length && playerField.length) {
            // Store all players and their data
            const allPlayerOptions = playerField.find('option').clone();
            
            positionField.on('change', function() {
                const selectedPosition = $(this).val();
                
                if (!selectedPosition) {
                    // Reset to all players
                    playerField.html(allPlayerOptions);
                    return;
                }
                
                // Filter players based on position
                const positionMap = {
                    'ATT': ['ST', 'LW', 'RW'],
                    'MID': ['CAM', 'CM', 'CDM'],
                    'DEF': ['LB', 'CB', 'RB'],
                    'GK': ['GK']
                };
                
                const validPositions = positionMap[selectedPosition] || [];
                
                // Clear and rebuild player dropdown
                playerField.html('<option value=\"\">---------</option>');
                
                allPlayerOptions.each(function() {
                    const optionText = $(this).text();
                    const playerPosition = optionText.match(/\\(([^)]+)\\)/);
                    
                    if (playerPosition && validPositions.includes(playerPosition[1])) {
                        playerField.append($(this).clone());
                    }
                });
            });
            
            // Auto-populate stats when player is selected
            playerField.on('change', function() {
                const selectedOption = $(this).find('option:selected');
                const optionText = selectedOption.text();
                
                // Extract skill rating from option text
                const skillRatingMatch = optionText.match(/Skill: ([\\d.]+)/);
                
                if (skillRatingMatch) {
                    // Fetch player stats via AJAX
                    const playerId = $(this).val();
                    
                    if (playerId) {
                        fetchPlayerStats(playerId);
                    }
                }
            });
        }
    }
    
    function setupTOTWInlines() {
        // Handle inline formsets
        $('.inline-group').on('change', 'select[id$=\"-position\"]', function() {
            const row = $(this).closest('.inline-related');
            const playerSelect = row.find('select[id$=\"-player\"]');
            const selectedPosition = $(this).val();
            
            if (!selectedPosition || !playerSelect.length) return;
            
            // Store original options
            if (!playerSelect.data('original-options')) {
                playerSelect.data('original-options', playerSelect.find('option').clone());
            }
            
            const allOptions = playerSelect.data('original-options');
            
            // Filter by position
            const positionMap = {
                'ATT': ['ST', 'LW', 'RW'],
                'MID': ['CAM', 'CM', 'CDM'],
                'DEF': ['LB', 'CB', 'RB'],
                'GK': ['GK']
            };
            
            const validPositions = positionMap[selectedPosition] || [];
            
            playerSelect.html('<option value=\"\">---------</option>');
            
            allOptions.each(function() {
                const optionText = $(this).text();
                const playerPosition = optionText.match(/\\(([^)]+)\\)/);
                
                if (playerPosition && validPositions.includes(playerPosition[1])) {
                    playerSelect.append($(this).clone());
                }
            });
        });
        
        // Auto-populate stats on player selection
        $('.inline-group').on('change', 'select[id$=\"-player\"]', function() {
            const playerId = $(this).val();
            const row = $(this).closest('.inline-related');
            
            if (playerId) {
                fetchPlayerStatsForInline(playerId, row);
            }
        });
    }
    
    function fetchPlayerStats(playerId) {
        // Use Django admin API or custom endpoint
        $.ajax({
            url: `/admin/league/player/${playerId}/stats/`,
            method: 'GET',
            success: function(data) {
                // Populate readonly fields
                $('#id_games_played').val(data.appearances || 0);
                $('#id_goals').val(data.goals || 0);
                $('#id_assists').val(data.assists || 0);
                $('#id_clean_sheets').val(data.clean_sheets || 0);
                $('#id_avg_rating').val(data.rating || 0);
                $('#id_skill_rating').val(data.skill_rating || 0);
            },
            error: function() {
                console.log('Could not fetch player stats');
            }
        });
    }
    
    function fetchPlayerStatsForInline(playerId, row) {
        // For inline forms
        $.ajax({
            url: `/admin/league/player/${playerId}/stats/`,
            method: 'GET',
            success: function(data) {
                row.find('input[id$=\"-games_played\"]').val(data.appearances || 0);
                row.find('input[id$=\"-goals\"]').val(data.goals || 0);
                row.find('input[id$=\"-assists\"]').val(data.assists || 0);
                row.find('input[id$=\"-clean_sheets\"]').val(data.clean_sheets || 0);
                row.find('input[id$=\"-avg_rating\"]').val(data.rating || 0);
                row.find('input[id$=\"-skill_rating\"]').val(data.skill_rating || 0);
            },
            error: function() {
                console.log('Could not fetch player stats for inline');
            }
        });
    }
    
})(django.jQuery);
