#![allow(unused)]
use std::{collections::{HashSet, HashMap}, env};

extern crate bit_vec;

mod domain_description;
mod graph_lib;
mod heuristics;
mod relaxation;
mod search;
mod task_network;

use crate::search::fixed_method::heuristic_factory;
use crate::search::{HeuristicType, SearchResult};
use domain_description::{read_json_domain, FONDProblem};
use heuristics::{h_add, h_ff, h_max};
use relaxation::RelaxedComposition;
use search::{
    astar::AStarResult,
    goal_checks::{is_goal_strong_od, is_goal_weak_ld},
    search_node::{get_successors_systematic, SearchNode},
};
use task_network::HTN;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        println!("The path to the problem file is not given.");
        return;
    }
    let problem = read_json_domain(&args[1]);

    // TODO: Refactor flexible method and fixed method to accept
    // heuristic input of the same type, so we only need one of the
    // following two match expressions

    let heuristic_flexible = match args.get(3) {
        Some(flag) => match flag.as_str() {
            "--add" => {
                println!("Using Add heuristic");
                HeuristicType::HAdd
            },
            "--max" => {
                println!("Using Max heuristic");
                HeuristicType::HMax
            },
            "--ff" => {
                println!("Using FF heuristic");
                HeuristicType::HFF
            },
            _ => panic!("Unknown heuristic")
        },
        None => {
            panic!("Expected heuristic flag")
        }
    };

    let heuristic_fixed = match args.get(3) {
        Some(flag) => match flag.as_str() {
            "--add" => {
                heuristic_factory::create_function_with_heuristic(h_add)
            },
            "--max" => {
                heuristic_factory::create_function_with_heuristic(h_max)
            },
            "--ff" => {
                heuristic_factory::create_function_with_heuristic(h_ff)
            },
            _ => panic!("Did not recognise flag {}", flag),
        },
        None => {
            panic!("Expected heuristic flag");
        }
    };

    match args.get(2) {
        Some(flag) => match flag.as_str() {
            "--fixed" => {
                println!("Running fixed method solver");
                fixed_method(&problem, heuristic_fixed)
            },
            "--flexible" => {
                println!("Running method based solver");
                method_based(&problem, heuristic_flexible)
            },
            _ => panic!("Did not recognise flag {}", flag)
        },
        None => method_based(&problem, heuristic_flexible),
    }
}

fn method_based(problem: &FONDProblem, h_type: HeuristicType) {
    let (solution, stats) = search::AOStarSearch::run(problem, h_type);
    print!("{}", stats);
    match solution {
        SearchResult::Success(x) => {
            println!("makespan: {}", x.makespan);
            println!("policy enteries: {}", x.transitions.len());
            // if (stats.search_nodes < 50) {
            //     println!("***************************");
            //     println!("{}", x);
            // }
        }
        SearchResult::NoSolution => {
            println!("Problem has no solution");
        }
    }
}

fn fixed_method(problem: &FONDProblem, heuristic: heuristic_factory::HeuristicFn) {
    let (solution, stats) = search::fixed_method::astar::a_star_search(
        &problem,
        heuristic,
        get_successors_systematic,
        || 1.0,
        is_goal_strong_od,
    );
    println!("{}", stats);
    // println!(
    //     "Number of maybe-isomorphic buckets: {}",
    //     stats.space.maybe_isomorphic_buckets.len()
    // );
    if let AStarResult::Strong(policy) = solution {
        println!("Solution was found");
        println!("# of policy enteries: {}", policy.transitions.len());
        // if (stats.space.total_nodes < 50) {
        //     println!("***************************");
        //     println!("{}", policy);
        // }
    } else {
        println!("Problem has no solution");
    }
    // if (stats.space.total_nodes < 50) {
    //     println!("{}", stats.space.to_string(problem));
    // }
}
