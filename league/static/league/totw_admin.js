(function() {
    'use strict';
    
    // Use Django's jQuery
    var $ = django.jQuery;
    
    $(document).ready(function() {
        console.log('TOTW admin JS loaded');
        
        // Wait for admin to fully initialize
        setTimeout(function() {
            if (window.location.href.indexOf('/league/teamoftheweekselection/') > -1) {
                console.log('Setting up TOTW selection admin');
                setupTOTWSelectionAdmin();
            }
            
            if (window.location.href.indexOf('/league/teamoftheweek/') > -1) {
                console.log('Setting up TOTW inlines');
                setupTOTWInlines();
            }
        }, 500);
    });
    
    function setupTOTWSelectionAdmin() {
        var positionField = $('#id_position');
        var playerField = $('#id_player');
        
        console.log('Position field found:', positionField.length);
        console.log('Player field found:', playerField.length);
        
        if (positionField.length === 0 || playerField.length === 0) {
            console.error('Could not find fields!');
            return;
        }
        
        // Store all player options
        var allPlayerOptions = playerField.find('option').clone();
        console.log('Stored', allPlayerOptions.length, 'player options');
        
        // Position change handler
        positionField.on('change', function() {
            var selectedPosition = $(this).val();
            console.log('Position changed to:', selectedPosition);
            
            if (!selectedPosition) {
                playerField.html(allPlayerOptions.clone());
                return;
            }
            
            // Position mapping
            var positionMap = {
                'ATT': ['ST', 'LW', 'RW'],
                'MID': ['CAM', 'CM', 'CDM'],
                'DEF': ['LB', 'CB', 'RB'],
                'GK': ['GK']
            };
            
            var validPositions = positionMap[selectedPosition] || [];
            console.log('Filtering for:', validPositions);
            
            // Rebuild dropdown
            playerField.html('<option value="">---------</option>');
            
            var filteredCount = 0;
            allPlayerOptions.each(function() {
                var $option = $(this);
                var optionText = $option.text();
                var optionValue = $option.val();
                
                if (!optionValue) return;
                
                // Extract position from "#1 - Name (POS) - Skill: 8.45"
                var match = optionText.match(/\(([A-Z]+)\)/);
                
                if (match && validPositions.indexOf(match[1]) > -1) {
                    playerField.append($option.clone());
                    filteredCount++;
                }
            });
            
            console.log('Filtered to', filteredCount, 'players');
        });
        
        // Player change handler
        playerField.on('change', function() {
            var playerId = $(this).val();
            console.log('Player selected:', playerId);
            
            if (playerId) {
                console.log('Making AJAX request to:', '/admin/league/player/' + playerId + '/stats/');
                
                $.ajax({
                    url: '/admin/league/player/' + playerId + '/stats/',
                    method: 'GET',
                    success: function(data) {
                        console.log('Stats received:', data);
                        
                        // Find the fields
                        var gamesField = $('#id_games_played');
                        var goalsField = $('#id_goals');
                        var assistsField = $('#id_assists');
                        var cleanSheetsField = $('#id_clean_sheets');
                        var avgRatingField = $('#id_avg_rating');
                        var skillRatingField = $('#id_skill_rating');
                        
                        console.log('Games field found:', gamesField.length);
                        console.log('Goals field found:', goalsField.length);
                        
                        // Set values
                        gamesField.val(data.appearances || 0);
                        goalsField.val(data.goals || 0);
                        assistsField.val(data.assists || 0);
                        cleanSheetsField.val(data.clean_sheets || 0);
                        avgRatingField.val(data.rating ? data.rating.toFixed(2) : '0.00');
                        skillRatingField.val(data.skill_rating ? data.skill_rating.toFixed(2) : '0.00');
                        
                        // Remove readonly attribute if present
                        gamesField.prop('readonly', false);
                        goalsField.prop('readonly', false);
                        assistsField.prop('readonly', false);
                        cleanSheetsField.prop('readonly', false);
                        avgRatingField.prop('readonly', false);
                        skillRatingField.prop('readonly', false);
                        
                        console.log('Stats populated! Games:', gamesField.val());
                    },
                    error: function(xhr, status, error) {
                        console.error('Error fetching stats');
                        console.error('Status:', status);
                        console.error('Error:', error);
                        console.error('Response:', xhr.responseText);
                    }
                });
            }
        });
    }
    
    function setupTOTWInlines() {
        var $ = django.jQuery;
        
        // Position change in inline
        $('.inline-group').on('change', 'select[id$="-position"]', function() {
            var $row = $(this).closest('.inline-related');
            var $playerSelect = $row.find('select[id$="-player"]');
            var selectedPosition = $(this).val();
            
            if (!selectedPosition || !$playerSelect.length) return;
            
            if (!$playerSelect.data('original-options')) {
                $playerSelect.data('original-options', $playerSelect.find('option').clone());
            }
            
            var allOptions = $playerSelect.data('original-options');
            
            var positionMap = {
                'ATT': ['ST', 'LW', 'RW'],
                'MID': ['CAM', 'CM', 'CDM'],
                'DEF': ['LB', 'CB', 'RB'],
                'GK': ['GK']
            };
            
            var validPositions = positionMap[selectedPosition] || [];
            
            $playerSelect.html('<option value="">---------</option>');
            
            allOptions.each(function() {
                var $option = $(this);
                var optionText = $option.text();
                var match = optionText.match(/\(([A-Z]+)\)/);
                
                if (match && validPositions.indexOf(match[1]) > -1) {
                    $playerSelect.append($option.clone());
                }
            });
        });
        
        // Player change in inline
        $('.inline-group').on('change', 'select[id$="-player"]', function() {
            var playerId = $(this).val();
            var $row = $(this).closest('.inline-related');
            
            if (playerId) {
                $.ajax({
                    url: '/admin/league/player/' + playerId + '/stats/',
                    method: 'GET',
                    success: function(data) {
                        $row.find('input[id$="-games_played"]').val(data.appearances || 0);
                        $row.find('input[id$="-goals"]').val(data.goals || 0);
                        $row.find('input[id$="-assists"]').val(data.assists || 0);
                        $row.find('input[id$="-clean_sheets"]').val(data.clean_sheets || 0);
                        $row.find('input[id$="-avg_rating"]').val(data.rating ? data.rating.toFixed(2) : '0.00');
                        $row.find('input[id$="-skill_rating"]').val(data.skill_rating ? data.skill_rating.toFixed(2) : '0.00');
                    }
                });
            }
        });
    }
    
})();
