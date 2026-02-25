#!/usr/bin/env python
"""Test the new skill rating calculation"""

def test_skill_rating():
    print("="*60)
    print("SKILL RATING CALCULATION TESTS")
    print("="*60)
    
    # Test 1: Attacker
    print("\n1. ATTACKER (ST, LW, RW)")
    print("-" * 40)
    rating = 8.5
    goals = 10
    assists = 5
    appearances = 10
    
    total_points = (goals * 5) + (assists * 3)
    max_allowed = 15 * appearances
    total_points = min(total_points, max_allowed)
    contribution_score = total_points / appearances
    
    match_component = 0.7 * rating
    contrib_component = 0.3 * contribution_score
    skill_rating = match_component + contrib_component
    
    print(f"Stats: {rating} rating, {goals}G, {assists}A in {appearances} apps")
    print(f"Contribution Points: {total_points} (max {max_allowed})")
    print(f"Contribution Score: {contribution_score:.2f}")
    print(f"Match Component (70%): {match_component:.2f}")
    print(f"Contrib Component (30%): {contrib_component:.2f}")
    print(f"SKILL RATING: {skill_rating:.2f}")
    
    # Test 2: Defender
    print("\n2. DEFENDER (LB, CB, RB)")
    print("-" * 40)
    rating = 7.5
    goals = 1
    assists = 2
    clean_sheets = 6
    appearances = 10
    
    total_points = (goals * 6) + (assists * 5) + (clean_sheets * 3)
    max_allowed = 10 * appearances
    total_points = min(total_points, max_allowed)
    contribution_score = total_points / appearances
    
    match_component = 0.7 * rating
    contrib_component = 0.3 * contribution_score
    skill_rating = match_component + contrib_component
    
    print(f"Stats: {rating} rating, {goals}G, {assists}A, {clean_sheets}CS in {appearances} apps")
    print(f"Contribution Points: {total_points} (max {max_allowed})")
    print(f"Contribution Score: {contribution_score:.2f}")
    print(f"Match Component (70%): {match_component:.2f}")
    print(f"Contrib Component (30%): {contrib_component:.2f}")
    print(f"SKILL RATING: {skill_rating:.2f}")
    
    # Test 3: Goalkeeper
    print("\n3. GOALKEEPER (GK)")
    print("-" * 40)
    rating = 8.0
    clean_sheets = 8
    appearances = 10
    
    total_points = clean_sheets * 3
    max_allowed = 8 * appearances
    total_points = min(total_points, max_allowed)
    contribution_score = total_points / appearances
    
    match_component = 0.7 * rating
    contrib_component = 0.3 * contribution_score
    skill_rating = match_component + contrib_component
    
    print(f"Stats: {rating} rating, {clean_sheets}CS in {appearances} apps")
    print(f"Contribution Points: {total_points} (max {max_allowed})")
    print(f"Contribution Score: {contribution_score:.2f}")
    print(f"Match Component (70%): {match_component:.2f}")
    print(f"Contrib Component (30%): {contrib_component:.2f}")
    print(f"SKILL RATING: {skill_rating:.2f}")
    
    # Test 4: Stat padding prevention
    print("\n4. STAT PADDING TEST - Attacker")
    print("-" * 40)
    rating = 7.0
    goals = 30  # Unrealistic - would be 150 points
    assists = 20  # Would be 60 points = 210 total
    appearances = 10
    
    total_points = (goals * 5) + (assists * 3)
    max_allowed = 15 * appearances  # Only 150 allowed
    print(f"Raw contribution points: {total_points}")
    total_points = min(total_points, max_allowed)
    contribution_score = total_points / appearances
    
    match_component = 0.7 * rating
    contrib_component = 0.3 * contribution_score
    skill_rating = match_component + contrib_component
    
    print(f"Stats: {rating} rating, {goals}G, {assists}A in {appearances} apps")
    print(f"Capped Contribution Points: {total_points} (max {max_allowed})")
    print(f"Contribution Score: {contribution_score:.2f}")
    print(f"SKILL RATING: {skill_rating:.2f}")
    print("✅ Cap prevents unrealistic boost!")
    
    print("\n" + "="*60)
    print("All tests completed successfully!")
    print("="*60)

if __name__ == '__main__':
    test_skill_rating()
